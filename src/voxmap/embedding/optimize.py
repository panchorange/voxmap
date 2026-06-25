"""埋め込みの RTF 最適化 (fp16 / melspec fbank) — 論文 proposed 手法のライブラリ実装。

これまで実験ごとの run.py に monkeypatch として重複していた fp16 / melspec を
ライブラリに昇格したもの。`load_diarization31_pipeline(embedding_dtype=...,
fbank_backend=...)` から呼ばれ、実験も studio も同一の最適化パスを使う。

- fp16: 埋め込みモデル body を float16 化 (fbank は float32 で計算後にキャスト。
  kaldi fbank が float16 を受けないため)。
- melspec: kaldi fbank (MPS で FFT が CPU フォールバック) を torchaudio の
  MelSpectrogram (MPS/CUDA ネイティブ) に差し替え。CAM++ のみ対応。per_chunk
  両対応。

参照: experiments/2026-05-07_pyannote31-pe/2026-05-21_voxconverse-relative-mcs-f001/run.py
"""

from __future__ import annotations

import types
from typing import Any

import torch
import torchaudio.transforms as T

from voxmap.embedding.wespeaker_emb import WeSpeakerEmbedder
from voxmap.log import get_logger
from voxmap.models.campplus import WeSpeakerCAMPlus
from voxmap.models.wespeaker_resnet34 import WeSpeakerResNet34

log = get_logger(__name__)

MELSPEC_PARAMS = dict(
    sample_rate=16_000,
    n_fft=512,
    win_length=400,
    hop_length=160,
    f_min=20.0,
    f_max=8000.0,
    n_mels=80,
    mel_scale="htk",
    window_fn=torch.hamming_window,
    power=2.0,
    center=False,
)


def _compute_fbank_melspec(waveforms: torch.Tensor, melspec: T.MelSpectrogram) -> torch.Tensor:
    """waveforms: (B, 1, samples) fp32 → fbank (B, T, n_mels)。"""
    x = waveforms.squeeze(1)
    mel = melspec(x)
    log_mel = torch.log(mel.clamp(min=1e-10))
    log_mel = log_mel.transpose(1, 2)
    return log_mel - log_mel.mean(dim=1, keepdim=True)


def apply_embedding_fp16(embedder: WeSpeakerEmbedder) -> None:
    """embedding body を float16 に切り替える。per_chunk / 通常モード両対応。"""
    model = embedder.model
    if isinstance(model, WeSpeakerResNet34):
        model.resnet = model.resnet.half()

        @torch.inference_mode()
        def _forward_resnet34_fp16(
            self: WeSpeakerEmbedder,
            waveform_batch: torch.Tensor,
            mask_batch: torch.Tensor,
        ) -> Any:
            wav = waveform_batch.to(self.device, dtype=torch.float32)
            masks = mask_batch.to(self.device, dtype=torch.float32)
            assert isinstance(self.model, WeSpeakerResNet34)
            fbank = self.model.compute_fbank(wav).half()
            emb = self.model.resnet(fbank, weights=masks.half())[1]
            return emb.float().cpu().numpy()

        embedder._forward_batch = types.MethodType(_forward_resnet34_fp16, embedder)  # type: ignore[method-assign]
    elif isinstance(model, WeSpeakerCAMPlus):
        model.campplus = model.campplus.half()

        @torch.inference_mode()
        def _forward_campplus_fp16(
            self: WeSpeakerEmbedder,
            waveform_batch: torch.Tensor,
            mask_batch: torch.Tensor,
        ) -> Any:
            wav = waveform_batch.to(self.device, dtype=torch.float32)
            masks = mask_batch.to(self.device, dtype=torch.float32)
            assert isinstance(self.model, WeSpeakerCAMPlus)
            fbank = self.model.compute_fbank(wav).half()
            emb = self.model.campplus(fbank, weights=masks.half())
            return emb.float().cpu().numpy()

        embedder._forward_batch = types.MethodType(_forward_campplus_fp16, embedder)  # type: ignore[method-assign]
    else:
        raise TypeError(f"unsupported embedder model: {type(model).__name__}")

    log.info("embedding_fp16_applied", model=type(model).__name__)


def apply_melspec_fbank(embedder: WeSpeakerEmbedder) -> None:
    """compute_fbank を kaldi (CPU) → MelSpectrogram (MPS/CUDA) に差し替える。

    apply_embedding_fp16 の後に呼ぶ前提。per_chunk モードでは
    _forward_batch_per_chunk を上書きする (encoder 共有 + pooling 話者分)。
    """
    model = embedder.model
    if not isinstance(model, WeSpeakerCAMPlus):
        raise TypeError(f"melspec fbank は CAM++ のみ対応: {type(model).__name__}")

    melspec = T.MelSpectrogram(**MELSPEC_PARAMS).to(embedder.device)

    if embedder.per_chunk:

        @torch.inference_mode()
        def _forward_campplus_per_chunk_melspec(
            self: WeSpeakerEmbedder,
            waveform_batch: torch.Tensor,
            mask_batch: torch.Tensor,
        ) -> Any:
            """waveform_batch (B, 1, samples), mask_batch (B, num_speakers, T_w)
            → embeddings (B, num_speakers, dim)。"""
            wav = waveform_batch.to(self.device, dtype=torch.float32)
            masks = mask_batch.to(self.device, dtype=torch.float32).half()
            assert isinstance(self.model, WeSpeakerCAMPlus)
            fbank = _compute_fbank_melspec(wav, melspec).half()
            features = self.model.campplus.forward_features(fbank)  # (B, C, T)
            per_speaker = [
                self.model.campplus.forward_pool(features, weights=masks[:, sp, :])
                for sp in range(masks.shape[1])
            ]
            stacked = torch.stack(per_speaker, dim=1)  # (B, num_speakers, dim)
            return stacked.float().cpu().numpy()

        embedder._forward_batch_per_chunk = types.MethodType(  # type: ignore[method-assign]
            _forward_campplus_per_chunk_melspec, embedder
        )
    else:

        @torch.inference_mode()
        def _forward_campplus_melspec(
            self: WeSpeakerEmbedder,
            waveform_batch: torch.Tensor,
            mask_batch: torch.Tensor,
        ) -> Any:
            wav = waveform_batch.to(self.device, dtype=torch.float32)
            masks = mask_batch.to(self.device, dtype=torch.float32)
            assert isinstance(self.model, WeSpeakerCAMPlus)
            fbank = _compute_fbank_melspec(wav, melspec).half()
            emb = self.model.campplus(fbank, weights=masks.half())
            return emb.float().cpu().numpy()

        embedder._forward_batch = types.MethodType(_forward_campplus_melspec, embedder)  # type: ignore[method-assign]

    log.info("melspec_fbank_applied", device=str(embedder.device), per_chunk=embedder.per_chunk)
