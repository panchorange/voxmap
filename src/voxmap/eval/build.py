"""Build a Diarization31Pipeline from an experiment `config.yaml` dict.

Experiment `run.py` files each re-declare the fp16 / melspec / per-chunk
monkeypatches inline. Analysis needs to reproduce *exactly* the pipeline an
experiment ran (otherwise the embeddings — and any clustering diagnosis built on
them — drift from the real result). This module is the single source of truth
for that build, so `scripts/analyze_pipeline.py` and per-analysis `analyze.py`
can do `build_pipeline_from_config(config)` and trust parity.

The accepted config shape is the experiment `pipeline:` block, e.g.
`experiments/2026-05-19_stride3-per-chunk/config.yaml`.
"""

from __future__ import annotations

import types
from typing import Any

import torch
import torchaudio.transforms as T

from voxmap.embedding.wespeaker_emb import WeSpeakerEmbedder
from voxmap.models.campplus import WeSpeakerCAMPlus
from voxmap.models.wespeaker_resnet34 import WeSpeakerResNet34
from voxmap.pipeline.diarization31 import Diarization31Pipeline, load_diarization31_pipeline

MELSPEC_PARAMS: dict[str, Any] = dict(
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


def resolve_device(name: str = "auto") -> torch.device:
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _compute_fbank_melspec(waveforms: torch.Tensor, melspec: T.MelSpectrogram) -> torch.Tensor:
    """waveforms: (B, 1, samples) fp32 → fbank (B, T, n_mels), CMN applied."""
    x = waveforms.squeeze(1)
    mel = melspec(x)
    log_mel = torch.log(mel.clamp(min=1e-10)).transpose(1, 2)
    return log_mel - log_mel.mean(dim=1, keepdim=True)


def apply_embedding_fp16(embedder: WeSpeakerEmbedder) -> None:
    """Switch the embedding body to float16. CAM++ / ResNet34, per_chunk-agnostic."""
    model = embedder.model
    if isinstance(model, WeSpeakerResNet34):
        model.resnet = model.resnet.half()

        @torch.inference_mode()
        def _forward_resnet34_fp16(
            self: WeSpeakerEmbedder, waveform_batch: torch.Tensor, mask_batch: torch.Tensor
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
            self: WeSpeakerEmbedder, waveform_batch: torch.Tensor, mask_batch: torch.Tensor
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


def apply_melspec_fbank(embedder: WeSpeakerEmbedder) -> None:
    """Swap compute_fbank kaldi (CPU) → MelSpectrogram (MPS/CUDA). CAM++ only.

    Call after apply_embedding_fp16. In per_chunk mode the encoder is run once per
    chunk and pooled per local speaker (mirrors experiment run.py).
    """
    model = embedder.model
    if not isinstance(model, WeSpeakerCAMPlus):
        raise TypeError(f"melspec fbank is CAM++ only: {type(model).__name__}")

    melspec = T.MelSpectrogram(**MELSPEC_PARAMS).to(embedder.device)

    if embedder.per_chunk:

        @torch.inference_mode()
        def _forward_campplus_per_chunk_melspec(
            self: WeSpeakerEmbedder, waveform_batch: torch.Tensor, mask_batch: torch.Tensor
        ) -> Any:
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
            self: WeSpeakerEmbedder, waveform_batch: torch.Tensor, mask_batch: torch.Tensor
        ) -> Any:
            wav = waveform_batch.to(self.device, dtype=torch.float32)
            masks = mask_batch.to(self.device, dtype=torch.float32)
            assert isinstance(self.model, WeSpeakerCAMPlus)
            fbank = _compute_fbank_melspec(wav, melspec).half()
            emb = self.model.campplus(fbank, weights=masks.half())
            return emb.float().cpu().numpy()

        embedder._forward_batch = types.MethodType(_forward_campplus_melspec, embedder)  # type: ignore[method-assign]


def build_pipeline_from_config(
    config: dict[str, Any], device: torch.device | None = None, token: str | None = None
) -> tuple[Diarization31Pipeline, torch.device]:
    """Build the exact pipeline an experiment config describes.

    `config` is the parsed experiment `config.yaml` (expects a `pipeline:` block).
    Applies `embedding_dtype: float16` and `fbank_backend: melspec` if set, so the
    captured embeddings match the experiment run.
    """
    pcfg = config["pipeline"]
    device = device or resolve_device(pcfg.get("device", "auto"))

    pipeline = load_diarization31_pipeline(
        segmentation_model=pcfg["segmentation_model"],
        embedding_model=pcfg["embedding_model"],
        threshold=float(pcfg["threshold"]),
        method=str(pcfg["method"]),
        min_cluster_size=int(pcfg["min_cluster_size"]),
        min_cluster_fraction=pcfg.get("min_cluster_fraction"),
        clustering=str(pcfg.get("clustering", "ahc")),
        embedding_batch_size=int(pcfg["embedding_batch_size"]),
        segmentation_batch_size=int(pcfg["segmentation_batch_size"]),
        embedding_exclude_overlap=bool(pcfg["embedding_exclude_overlap"]),
        min_duration_off=float(pcfg["min_duration_off"]),
        segmentation_step=pcfg.get("segmentation_step"),
        embedding_per_chunk=bool(pcfg.get("embedding_per_chunk", False)),
        device=device,
        token=token,
    )

    if pcfg.get("embedding_dtype") == "float16":
        apply_embedding_fp16(pipeline.embedder)
    if pcfg.get("fbank_backend") == "melspec":
        apply_melspec_fbank(pipeline.embedder)

    return pipeline, device
