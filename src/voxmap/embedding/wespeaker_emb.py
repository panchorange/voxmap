"""WeSpeaker-family embedding adapter for the diarization-3.1 flow.

For each (chunk, local_speaker) pair produced by the segmenter:
  1. Crop the chunk's waveform from the file (zero-pad past EOF).
  2. Select the speaker's frame-level activation as the embedding mask.
     If `exclude_overlap=True` and the speaker has enough non-overlapping
     frames, use only those (this matches pyannote/speaker-diarization-3.1).
  3. Batch and forward through the embedding model (ResNet34 / CAM++) to
     get a fixed-dim speaker vector.
  4. Reshape to (num_chunks, num_local_speakers, dim).

Output is consumed by the clustering stage of the pipeline.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from einops import rearrange
from pyannote.core import SlidingWindowFeature

from voxmap.models.campplus import WeSpeakerCAMPlus
from voxmap.models.wespeaker_resnet34 import WeSpeakerResNet34
from voxmap.types import Audio

type WeSpeakerCompatibleModel = WeSpeakerResNet34 | WeSpeakerCAMPlus


def _crop_padded(
    waveform: torch.Tensor, sample_rate: int, start: float, end: float
) -> torch.Tensor:
    """Crop waveform[start:end] in seconds, zero-padding past EOF.

    waveform : (channels, num_samples)
    Returns  : (channels, expected_samples)
    """
    expected = int(round((end - start) * sample_rate))
    s_idx = int(round(start * sample_rate))
    e_idx = s_idx + expected

    n_samples = waveform.shape[1]
    left_pad = max(0, -s_idx)
    right_pad = max(0, e_idx - n_samples)
    s_clipped = max(0, s_idx)
    e_clipped = min(n_samples, e_idx)

    cropped = waveform[:, s_clipped:e_clipped]
    if left_pad or right_pad:
        cropped = F.pad(cropped, (left_pad, right_pad))
    return cropped


class WeSpeakerEmbedder:
    """WeSpeaker-family embedder matching pyannote/speaker-diarization-3.1.

    Accepts any model exposing the WeSpeaker interface (`forward(waveforms,
    weights)`, `dimension`, `metric`, `min_num_samples`): currently
    `WeSpeakerResNet34` and `WeSpeakerCAMPlus`.

    `per_chunk=True` enables the SpeakerKit-style strategy (arXiv:2507.16136):
    run the heavy speaker-agnostic encoder ONCE per chunk and pool with each
    local-speaker mask separately. Output shape unchanged. Requires the model
    to expose `forward_features()` and `forward_pool()` (currently CAM++ only).
    In per-chunk mode, `batch_size` is interpreted as **chunks per encoder
    forward** (vs (chunk × speaker) pairs in the default mode).
    """

    def __init__(
        self,
        model: WeSpeakerCompatibleModel,
        batch_size: int = 32,
        exclude_overlap: bool = True,
        device: torch.device | None = None,
        per_chunk: bool = False,
    ) -> None:
        self.model = model.eval()
        self.batch_size = batch_size
        self.exclude_overlap = exclude_overlap
        self.device = device or torch.device("cpu")
        self.per_chunk = per_chunk
        if per_chunk and not (
            hasattr(model, "forward_features") and hasattr(model, "forward_pool")
        ):
            raise TypeError(
                f"per_chunk=True requires forward_features/forward_pool on the model; "
                f"{type(model).__name__} does not expose them."
            )
        self.model.to(self.device)

    @property
    def dimension(self) -> int:
        return self.model.dimension

    @property
    def metric(self) -> str:
        return self.model.metric

    @torch.inference_mode()
    def _forward_batch(self, waveform_batch: torch.Tensor, mask_batch: torch.Tensor) -> np.ndarray:
        wav = waveform_batch.to(self.device)
        masks = mask_batch.to(self.device)
        emb = self.model(wav, weights=masks)
        result: np.ndarray = emb.cpu().numpy()
        return result

    @torch.inference_mode()
    def _forward_batch_per_chunk(
        self, waveform_batch: torch.Tensor, mask_batch: torch.Tensor
    ) -> np.ndarray:
        """waveform_batch (B, 1, samples), mask_batch (B, num_speakers, num_frames)
        → embeddings (B, num_speakers, dim).

        Runs the speaker-agnostic encoder once per chunk, then pools with each
        local speaker mask.
        """
        wav = waveform_batch.to(self.device)
        masks = mask_batch.to(self.device)
        features = self.model.forward_features(wav)  # type: ignore[operator]  # (B, C, T)
        per_speaker = [
            self.model.forward_pool(features, weights=masks[:, sp, :])  # type: ignore[operator]
            for sp in range(masks.shape[1])
        ]
        stacked = torch.stack(per_speaker, dim=1)  # (B, num_speakers, dim)
        result: np.ndarray = stacked.cpu().numpy()
        return result

    def __call__(
        self,
        audio: Audio,
        binary_segmentations: SlidingWindowFeature,
        hook: Callable[..., Any] | None = None,
    ) -> np.ndarray:
        """Returns (num_chunks, num_local_speakers, dim) embeddings."""
        if self.per_chunk:
            return self._call_per_chunk(audio, binary_segmentations, hook)
        return self._call_per_speaker_masked(audio, binary_segmentations, hook)

    def _call_per_speaker_masked(
        self,
        audio: Audio,
        binary_segmentations: SlidingWindowFeature,
        hook: Callable[..., Any] | None = None,
    ) -> np.ndarray:
        num_chunks, num_frames, num_speakers = binary_segmentations.data.shape
        chunk_window = binary_segmentations.sliding_window
        duration = chunk_window.duration
        sample_rate = audio.sample_rate

        # min frames threshold for "is non-overlap mask informative enough"
        # (matches pyannote: ratio of min_num_samples / num_samples_in_chunk)
        if self.exclude_overlap:
            num_samples = duration * sample_rate
            min_num_frames = math.ceil(num_frames * self.model.min_num_samples / num_samples)
            clean_data = (np.sum(binary_segmentations.data, axis=2, keepdims=True) < 2).astype(
                np.float32
            )
            clean_segmentations = binary_segmentations.data * clean_data
        else:
            min_num_frames = -1
            clean_segmentations = binary_segmentations.data

        def iter_pairs() -> Iterator[tuple[torch.Tensor, torch.Tensor]]:
            for c in range(num_chunks):
                chunk_seg = chunk_window[c]  # pyannote.core.Segment(start, end)
                chunk_start = chunk_seg.start
                chunk_end = chunk_seg.end

                cropped = _crop_padded(audio.waveform, sample_rate, chunk_start, chunk_end)
                # ensure mono (downmix if needed) — speaker-diarization-3.1 uses mono="downmix"
                if cropped.shape[0] > 1:
                    cropped = cropped.mean(dim=0, keepdim=True)

                masks = np.nan_to_num(binary_segmentations.data[c], nan=0.0).astype(np.float32)
                clean_masks = np.nan_to_num(clean_segmentations[c], nan=0.0).astype(np.float32)

                # masks: (num_frames, num_speakers) — iterate per local speaker
                for sp in range(num_speakers):
                    mask = masks[:, sp]
                    clean_mask = clean_masks[:, sp]
                    used_mask = clean_mask if np.sum(clean_mask) > min_num_frames else mask
                    yield (
                        cropped.unsqueeze(0),  # (1, 1, samples)
                        torch.from_numpy(used_mask).unsqueeze(0),  # (1, num_frames)
                    )

        total_pairs = num_chunks * num_speakers
        batch_count = math.ceil(total_pairs / self.batch_size)
        if hook is not None:
            hook("embeddings", None, total=batch_count, completed=0)

        outputs: list[np.ndarray] = []
        batch_buf: list[tuple[torch.Tensor, torch.Tensor]] = []
        completed = 0
        for pair in iter_pairs():
            batch_buf.append(pair)
            if len(batch_buf) == self.batch_size:
                outputs.append(self._flush_batch(batch_buf))
                batch_buf.clear()
                completed += 1
                if hook is not None:
                    hook("embeddings", outputs[-1], total=batch_count, completed=completed)

        if batch_buf:
            outputs.append(self._flush_batch(batch_buf))
            completed += 1
            if hook is not None:
                hook("embeddings", outputs[-1], total=batch_count, completed=completed)

        stacked = np.vstack(outputs)  # (num_chunks * num_speakers, dim)
        embeddings = rearrange(stacked, "(c s) d -> c s d", c=num_chunks)
        return embeddings

    def _call_per_chunk(
        self,
        audio: Audio,
        binary_segmentations: SlidingWindowFeature,
        hook: Callable[..., Any] | None = None,
    ) -> np.ndarray:
        """Per-chunk strategy: shared encoder forward, per-speaker pooling."""
        num_chunks, num_frames, num_speakers = binary_segmentations.data.shape
        chunk_window = binary_segmentations.sliding_window
        duration = chunk_window.duration
        sample_rate = audio.sample_rate

        if self.exclude_overlap:
            num_samples = duration * sample_rate
            min_num_frames = math.ceil(num_frames * self.model.min_num_samples / num_samples)
            clean_data = (np.sum(binary_segmentations.data, axis=2, keepdims=True) < 2).astype(
                np.float32
            )
            clean_segmentations = binary_segmentations.data * clean_data
        else:
            min_num_frames = -1
            clean_segmentations = binary_segmentations.data

        def iter_chunks() -> Iterator[tuple[torch.Tensor, np.ndarray]]:
            for c in range(num_chunks):
                chunk_seg = chunk_window[c]
                cropped = _crop_padded(audio.waveform, sample_rate, chunk_seg.start, chunk_seg.end)
                if cropped.shape[0] > 1:
                    cropped = cropped.mean(dim=0, keepdim=True)

                masks = np.nan_to_num(binary_segmentations.data[c], nan=0.0).astype(np.float32)
                clean_masks = np.nan_to_num(clean_segmentations[c], nan=0.0).astype(np.float32)

                # decide per-speaker mask: clean (no-overlap) if enough frames, else raw
                chunk_masks = np.empty((num_speakers, num_frames), dtype=np.float32)
                for sp in range(num_speakers):
                    raw = masks[:, sp]
                    clean = clean_masks[:, sp]
                    chunk_masks[sp] = clean if np.sum(clean) > min_num_frames else raw
                yield (
                    cropped.unsqueeze(0),
                    chunk_masks,
                )  # (1, 1, samples), (num_speakers, num_frames)

        batch_count = math.ceil(num_chunks / self.batch_size)
        if hook is not None:
            hook("embeddings", None, total=batch_count, completed=0)

        outputs: list[np.ndarray] = []
        wav_buf: list[torch.Tensor] = []
        mask_buf: list[np.ndarray] = []
        completed = 0
        for wav, chunk_masks in iter_chunks():
            wav_buf.append(wav)
            mask_buf.append(chunk_masks)
            if len(wav_buf) == self.batch_size:
                outputs.append(self._flush_batch_per_chunk(wav_buf, mask_buf))
                wav_buf.clear()
                mask_buf.clear()
                completed += 1
                if hook is not None:
                    hook("embeddings", outputs[-1], total=batch_count, completed=completed)

        if wav_buf:
            outputs.append(self._flush_batch_per_chunk(wav_buf, mask_buf))
            completed += 1
            if hook is not None:
                hook("embeddings", outputs[-1], total=batch_count, completed=completed)

        return np.vstack(outputs)  # (num_chunks, num_speakers, dim)

    def _flush_batch(self, pairs: list[tuple[torch.Tensor, torch.Tensor]]) -> np.ndarray:
        wavs = torch.vstack([p[0] for p in pairs])
        masks = torch.vstack([p[1] for p in pairs])
        return self._forward_batch(wavs, masks)

    def _flush_batch_per_chunk(
        self, wavs_list: list[torch.Tensor], masks_list: list[np.ndarray]
    ) -> np.ndarray:
        wavs = torch.vstack(wavs_list)  # (B, 1, samples)
        masks = torch.from_numpy(np.stack(masks_list))  # (B, num_speakers, num_frames)
        return self._forward_batch_per_chunk(wavs, masks)


def load_wespeaker_embedder(
    model_id: str = "pyannote/wespeaker-voxceleb-resnet34-LM",
    batch_size: int = 32,
    exclude_overlap: bool = True,
    device: torch.device | None = None,
    token: str | None = None,
    cache_dir: str | None = None,
    per_chunk: bool = False,
) -> WeSpeakerEmbedder:
    """Convenience: bootstrap WeSpeaker ResNet34 weights and wrap in the adapter."""
    resnet34 = WeSpeakerResNet34.from_pyannote(model_id, token=token, cache_dir=cache_dir)
    return WeSpeakerEmbedder(
        model=resnet34,
        batch_size=batch_size,
        exclude_overlap=exclude_overlap,
        device=device,
        per_chunk=per_chunk,
    )


def load_campplus_embedder(
    model_id: str = "Wespeaker/wespeaker-voxceleb-campplus",
    batch_size: int = 32,
    exclude_overlap: bool = True,
    device: torch.device | None = None,
    token: str | None = None,
    cache_dir: str | None = None,
    per_chunk: bool = False,
) -> WeSpeakerEmbedder:
    """Convenience: bootstrap WeSpeaker CAM++ weights and wrap in the adapter."""
    campplus = WeSpeakerCAMPlus.from_wespeaker(repo_id=model_id, token=token, cache_dir=cache_dir)
    return WeSpeakerEmbedder(
        model=campplus,
        batch_size=batch_size,
        exclude_overlap=exclude_overlap,
        device=device,
        per_chunk=per_chunk,
    )
