"""Parakeet **hybrid (tdt_ctc)** ASR adapter — CTC / TDT 切替 + word timestamps。

`ParakeetASR` ([parakeet.py]) は v3 (TDT-only) を自前 encoder で動かす本番 Phase 1 専用。
本アダプタは ASR-diarization 統合実験向けに、**hybrid tdt_ctc モデル** (例:
parakeet-tdt_ctc-110m) を NeMo のまま読み込み、CTC head (速い) か TDT head を選んで
word timestamp 付き `Transcript` を返す。

速度計測 (profiles/2026-05-31_parakeet-110m-vs-0.6b-encdec-mps) で 110M+CTC が MPS RTF
~0.002 (0.6b 比 3.5×) と判明したのを受け、統合パイプラインの ASR コンポーネントとして使う。

長尺音声は固定 chunk で分割し、各 chunk の word timestamp を chunk 先頭時刻だけオフセット
して連結する (MPS/CPU が 1 ミーティング全体を載せられないため)。
"""

from __future__ import annotations

from typing import Any, Literal, cast

import torch

from voxmap.types import Audio, Transcript, Word

# window_stride 10ms x subsampling_factor 8 = 80ms per encoder frame
FRAME_SEC = 0.01 * 8

Decode = Literal["ctc", "tdt"]


class ParakeetHybridASR:
    def __init__(
        self,
        model_name: str = "nvidia/parakeet-tdt_ctc-110m",
        decode: Decode = "ctc",
        device: str = "mps",
        dtype: str = "fp16",
        chunk_sec: float = 30.0,
    ) -> None:
        try:
            import nemo.collections.asr as nemo_asr
            from omegaconf import DictConfig, OmegaConf
        except ImportError as e:
            raise ImportError(
                "NeMo が未インストールです。\n  uv pip install 'nemo_toolkit[asr]'"
            ) from e

        self.device = device
        self.dtype = dtype
        self.chunk_sec = chunk_sec
        self.decode = decode

        model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_name)
        # CTC head は decode="ctc" のときだけ必須。TDT-only モデル (例: parakeet-tdt-0.6b-v2)
        # は ctc_decoder を持たないが、decode="tdt" なら RNNT/TDT head で動かせる。
        if decode == "ctc" and not hasattr(model, "ctc_decoder"):
            raise ValueError(f"{model_name} は CTC head を持たないため decode='ctc' で使えません")

        # word-level timestamps を有効化 (TDT/CTC 各 decoding に設定)
        if decode == "tdt":
            cfg: dict[str, Any] = cast(
                "dict[str, Any]", OmegaConf.to_container(model.cfg.decoding, resolve=True)
            )
            cfg["compute_timestamps"] = True
            cfg["rnnt_timestamp_type"] = "word"
            # hybrid (tdt_ctc) は decoder_type で head を選ぶ必要があるが、純 RNNT/TDT
            # モデル (parakeet-tdt-0.6b-v2 等) の change_decoding_strategy は decoder_type を
            # 受け付けない。CTC head の有無で hybrid かどうかを判定して分岐する。
            if hasattr(model, "ctc_decoder"):
                model.change_decoding_strategy(DictConfig(cfg), decoder_type="rnnt")
            else:
                model.change_decoding_strategy(DictConfig(cfg))
        else:
            cfg = cast(
                "dict[str, Any]",
                OmegaConf.to_container(model.cfg.aux_ctc.decoding, resolve=True),
            )
            cfg["compute_timestamps"] = True
            cfg["ctc_timestamp_type"] = "word"
            model.change_decoding_strategy(DictConfig(cfg), decoder_type="ctc")

        model = model.to(device)
        if dtype == "fp16":
            model = model.half()
        model.eval()
        model.preprocessor.featurizer.dither = 0.0
        self._model = model

    @torch.no_grad()
    def __call__(self, audio: Audio) -> Transcript:
        wav = self._to_mono_16k(audio)
        sr = 16000
        chunk_samples = int(self.chunk_sec * sr)
        words: list[Word] = []
        for start in range(0, wav.shape[0], chunk_samples):
            chunk = wav[start : start + chunk_samples]
            words.extend(self._transcribe_chunk(chunk, sr, start / sr))
        return Transcript(words=words)

    def _transcribe_chunk(self, chunk: torch.Tensor, sr: int, time_offset: float) -> list[Word]:
        model = self._model
        signal = chunk.unsqueeze(0).to(self.device)
        length = torch.tensor([chunk.shape[0]], dtype=torch.int64, device=self.device)

        processed, proc_len = model.preprocessor(input_signal=signal, length=length)
        if self.dtype == "fp16":
            processed = processed.half()
        encoded, encoded_len = model.encoder(audio_signal=processed, length=proc_len)

        if self.decode == "tdt":
            hyps = model.decoding.rnnt_decoder_predictions_tensor(
                encoder_output=encoded, encoded_lengths=encoded_len, return_hypotheses=True
            )
        else:
            logits = model.ctc_decoder(encoder_output=encoded)
            hyps = model.ctc_decoding.ctc_decoder_predictions_tensor(
                logits, decoder_lengths=encoded_len, return_hypotheses=True
            )
        hyp_raw = hyps[0] if isinstance(hyps, tuple) else hyps
        hyp = hyp_raw[0] if isinstance(hyp_raw, list) else hyp_raw
        return self._extract_words(hyp, time_offset)

    @staticmethod
    def _extract_words(hyp: object, time_offset: float) -> list[Word]:
        ts = getattr(hyp, "timestamp", None) or getattr(hyp, "timestep", None)
        if not isinstance(ts, dict) or "word" not in ts:
            return []
        words: list[Word] = []
        for w in ts["word"]:
            # frame offset (start_offset/end_offset) か秒 (start/end) のどちらかが入る
            if "start_offset" in w:
                start = w["start_offset"] * FRAME_SEC
                end = w["end_offset"] * FRAME_SEC
            else:
                start = float(w["start"])
                end = float(w["end"])
            text = w.get("word", w.get("char", ""))
            words.append(Word(text=text, start=start + time_offset, end=end + time_offset))
        return words

    @staticmethod
    def _to_mono_16k(audio: Audio) -> torch.Tensor:
        import torchaudio

        wav = audio.waveform
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)
        if audio.sample_rate != 16000:
            wav = torchaudio.functional.resample(wav, audio.sample_rate, 16000)
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)
        return wav.squeeze(0).float()
