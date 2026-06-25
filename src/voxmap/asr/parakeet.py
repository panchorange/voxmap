"""Parakeet ASR adapter (Phase 1: self-implemented Conformer encoder).

Wires:
  preprocess (NeMo mel)  →  vendored ConformerEncoder (voxmap.models.conformer)
  →  decode (NeMo RNNT/TDT greedy, word timestamps)

The encoder is our own `ConformerEncoder` with weights copied from the loaded
NeMo model (`nemo_model.encoder.state_dict()`). preprocess and decode stay on
NeMo for now (ADR 2026-05-28_vendor_parakeet_conformer, Phase 1).

Long audio is processed in fixed chunks (MPS/CPU cannot fit a full meeting);
word timestamps are offset per chunk and concatenated.
"""

from __future__ import annotations

from typing import Any, cast

import torch

from voxmap.models.conformer import ConformerEncoder
from voxmap.types import Audio, Transcript, Word

_MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v3"
# window_stride 10ms x subsampling_factor 8 = 80ms per encoder frame
FRAME_SEC = 0.01 * 8


class ParakeetASR:
    def __init__(
        self,
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

        model = nemo_asr.models.ASRModel.from_pretrained(model_name=_MODEL_NAME)

        # word-level timestamps を有効化
        decoding_cfg: dict[str, Any] = cast(
            "dict[str, Any]", OmegaConf.to_container(model.cfg.decoding, resolve=True)
        )
        decoding_cfg["compute_timestamps"] = True
        decoding_cfg["rnnt_timestamp_type"] = "word"
        model.change_decoding_strategy(DictConfig(decoding_cfg))

        model = model.to(device)
        if dtype == "fp16":
            model = model.half()
        model.eval()
        self._model = model

        # self 実装 encoder を構築し NeMo の重みをロード
        encoder = ConformerEncoder(
            feat_in=model.cfg.encoder.feat_in,
            n_layers=model.cfg.encoder.n_layers,
            d_model=model.cfg.encoder.d_model,
            n_heads=model.cfg.encoder.n_heads,
            ff_expansion_factor=model.cfg.encoder.ff_expansion_factor,
            conv_kernel_size=model.cfg.encoder.conv_kernel_size,
            subsampling_factor=model.cfg.encoder.subsampling_factor,
            subsampling_conv_channels=model.cfg.encoder.subsampling_conv_channels,
            pos_emb_max_len=model.cfg.encoder.pos_emb_max_len,
            use_bias=model.cfg.encoder.use_bias,
        )
        encoder.load_state_dict(model.encoder.state_dict())
        encoder = encoder.to(device)
        if dtype == "fp16":
            encoder = encoder.half()
        encoder.eval()
        self.encoder = encoder

    @torch.no_grad()
    def __call__(self, audio: Audio) -> Transcript:
        wav = self._to_mono_16k(audio)
        sr = 16000
        chunk_samples = int(self.chunk_sec * sr)
        words: list[Word] = []

        for start in range(0, wav.shape[0], chunk_samples):
            chunk = wav[start : start + chunk_samples]
            time_offset = start / sr
            words.extend(self._transcribe_chunk(chunk, sr, time_offset))

        return Transcript(words=words)

    def _transcribe_chunk(self, chunk: torch.Tensor, sr: int, time_offset: float) -> list[Word]:
        model = self._model
        signal = chunk.unsqueeze(0).to(self.device)
        length = torch.tensor([chunk.shape[0]], dtype=torch.int64, device=self.device)

        processed, proc_len = model.preprocessor(input_signal=signal, length=length)
        if self.dtype == "fp16":
            processed = processed.half()

        encoded, encoded_len = self.encoder(processed, proc_len)  # ← self 実装 encoder

        hyps = model.decoding.rnnt_decoder_predictions_tensor(
            encoder_output=encoded,
            encoded_lengths=encoded_len,
            return_hypotheses=True,
        )
        hyp_raw = hyps[0]
        hyp = hyp_raw[0] if isinstance(hyp_raw, list) else hyp_raw
        return self._extract_words(hyp, time_offset)

    @staticmethod
    def _extract_words(hyp: object, time_offset: float) -> list[Word]:
        ts = getattr(hyp, "timestep", None)
        if not isinstance(ts, dict) or "word" not in ts:
            return []
        return [
            Word(
                text=w["word"],
                start=w["start_offset"] * FRAME_SEC + time_offset,
                end=w["end_offset"] * FRAME_SEC + time_offset,
            )
            for w in ts["word"]
        ]

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
