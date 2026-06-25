"""正解 RTTM から enrollment ギャラリー (npy) を作る (会議内エンロールの実装)。

studio backend と同じ埋め込みモデルで RTTM の各話者を埋め込み、Gallery.save で
speaker ごとの npy を書き出す。backend は config の recommend.gallery_path から読む。
これで「アノテーション済みの会議の話者ベクトル」を使ってレコメンドを試せる。

使い方 (apps/studio/backend で):
  uv run python scripts/build_gallery.py \
    --audio ../../../data/raw/ami/audio/EN2002a.Mix-Headset.wav \
    --rttm  ../../../data/raw/ami/setup/word_and_vocalsounds/rttms/test/EN2002a.rttm \
    --out   ./gallery/EN2002a

その後 app/config.yaml の recommend.gallery_path を ./gallery/EN2002a にして backend 起動。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
import torchaudio.transforms as T
import yaml
from numpy.typing import NDArray
from voxmap.embedding.optimize import MELSPEC_PARAMS, _compute_fbank_melspec
from voxmap.embedding.wespeaker_emb import _crop_padded
from voxmap.io.audio import load_audio
from voxmap.io.rttm import read_rttm
from voxmap.models.campplus import WeSpeakerCAMPlus
from voxmap.recommend.enrollment import Gallery
from voxmap.types import Audio, Segment

from app.diarize import build_pipeline, resolve_device

MIN_DUR = 1.0  # 短い turn は埋め込みが不安定なので除外
MAX_PER_SPK = 50  # 1話者あたり最大参照数 (長い順)
CLIP_SEC = 5.0  # 試聴用 代表クリップの長さ (最長 turn の先頭)


@torch.inference_mode()
def _embed_recipe(
    model: WeSpeakerCAMPlus,
    audio: Audio,
    segments: list[Segment],
    device: torch.device,
    fbank_backend: str,
    dtype: str,
    batch_size: int = 32,
) -> NDArray[np.float32]:
    """各 turn を **推論と同じ recipe (fbank_backend / dtype)** で埋め込む (uniform pool)。

    重要: gallery は推論側 (Diarization31 の最適化済み embedder) と同じ特徴空間に
    無いと cos が比較不能になる。melspec/fp16 を config どおりに適用して揃える。
    weights=None = crop 全体の一様プーリング (= この turn を埋め込む)。
    """
    melspec = T.MelSpectrogram(**MELSPEC_PARAMS).to(device) if fbank_backend == "melspec" else None
    min_samples = model.min_num_samples
    crops: list[torch.Tensor] = []
    for seg in segments:
        crop = _crop_padded(audio.waveform, audio.sample_rate, seg.start, seg.end)
        if crop.shape[0] > 1:
            crop = crop.mean(dim=0, keepdim=True)  # mono 化
        if crop.shape[1] < min_samples:
            crop = F.pad(crop, (0, min_samples - crop.shape[1]))
        crops.append(crop)

    order = sorted(range(len(crops)), key=lambda i: crops[i].shape[1])
    results: list[tuple[int, NDArray[np.float32]]] = []
    for start in range(0, len(order), batch_size):
        idxs = order[start : start + batch_size]
        maxlen = max(crops[i].shape[1] for i in idxs)
        wavs = torch.stack(
            [F.pad(crops[i], (0, maxlen - crops[i].shape[1])) for i in idxs]
        ).to(device, dtype=torch.float32)
        if melspec is not None:
            fbank = _compute_fbank_melspec(wavs, melspec)
        else:
            fbank = model.compute_fbank(wavs)
        if dtype == "float16":
            fbank = fbank.half()  # campplus body が half のとき dtype を合わせる
        emb = model.campplus(fbank, weights=None)
        arr = np.asarray(emb.float().cpu().numpy(), dtype=np.float32)
        results.extend((i, arr[j]) for j, i in enumerate(idxs))

    results.sort(key=lambda r: r[0])
    return np.vstack([e for _, e in results]).astype(np.float32)


def _save_clip(audio_path: str, start: float, dur: float, out_path: Path) -> None:
    """試聴用に、元音声の [start, start+dur] を mono wav で書き出す (UI の右側 ▶ 用)。"""
    info = sf.info(audio_path)
    sr = int(info.samplerate)
    data, _ = sf.read(
        audio_path, start=int(start * sr), stop=int((start + dur) * sr), dtype="float32"
    )
    if data.ndim > 1:
        data = data[:, 0]  # mono 化
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out_path, data, sr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--rttm", required=True)
    ap.add_argument("--out", required=True)
    default_config = Path(__file__).resolve().parent.parent / "app" / "config.yaml"
    ap.add_argument("--config", default=str(default_config))
    args = ap.parse_args()

    with Path(args.config).open() as f:
        config = yaml.safe_load(f)
    p = config["pipeline"]
    device = resolve_device(str(p.get("device", "auto")))
    pipeline = build_pipeline(config, device)
    model = pipeline.embedder.model
    if not isinstance(model, WeSpeakerCAMPlus):
        raise TypeError(f"build_gallery は CAM++ のみ対応: {type(model).__name__}")
    fbank_backend = str(p.get("fbank_backend", "kaldi"))
    dtype = str(p.get("embedding_dtype", "float32"))

    audio = load_audio(args.audio)
    diar = read_rttm(args.rttm)

    by_spk: dict[str, list[Segment]] = {}
    for t in diar.turns:
        if t.segment.duration >= MIN_DUR:
            by_spk.setdefault(t.speaker, []).append(t.segment)

    gallery = Gallery()
    for spk, segs in by_spk.items():
        chosen = sorted(segs, key=lambda s: s.duration, reverse=True)[:MAX_PER_SPK]
        emb = _embed_recipe(model, audio, chosen, device, fbank_backend, dtype)
        gallery.add(spk, emb)
        # 代表クリップ (最長 turn の先頭 CLIP_SEC) を audio/ に保存
        rep = chosen[0]
        audio_dir = Path(args.out) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        _save_clip(
            args.audio, rep.start, min(rep.duration, CLIP_SEC), audio_dir / f"{spk}.wav"
        )
        print(f"{spk}: {len(chosen)} refs -> {emb.shape} (+clip)")

    vector_dir = Path(args.out) / "vector"
    vector_dir.mkdir(parents=True, exist_ok=True)
    gallery.save(vector_dir)
    print(f"saved gallery to {args.out}/vector/ ({len(gallery)} speakers)")


if __name__ == "__main__":
    main()
