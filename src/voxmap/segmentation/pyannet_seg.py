"""PyanNet-based segmenter — sliding window inference + powerset → multilabel.

Replicates `pyannote.audio.Inference.slide()` for the diarization use case:
  - sliding window of `duration` (10s) with `step` (1s) over the waveform
  - batched forward through PyanNet
  - powerset (7-class) → multilabel (3-class) conversion
  - last incomplete chunk is zero-padded and processed separately

Returns a `SlidingWindowFeature` with shape (num_chunks, num_frames, 3) so that
downstream code (speaker_count, get_embeddings, reconstruct) sees the same
contract as pyannote's pipeline.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from einops import rearrange
from pyannote.audio.utils.powerset import Powerset
from pyannote.core import SlidingWindow, SlidingWindowFeature

from voxmap.models.pyannet import PyanNet
from voxmap.types import Audio


class PyanNetSegmenter:
    """Sliding-window powerset segmenter using a vendored PyanNet."""

    def __init__(
        self,
        model: PyanNet,
        duration: float = 10.0,
        step: float | None = None,
        batch_size: int = 32,
        device: torch.device | None = None,
    ) -> None:
        self.model = model.eval()
        self._duration = duration
        # pyannote's segmentation_step default is 0.1 (10% of duration → 1.0s for 10s chunks)
        self.step = step if step is not None else 0.1 * duration
        self.batch_size = batch_size
        self.device = device or torch.device("cpu")
        self.model.to(self.device)

        spec = model.specifications
        if spec is None or not getattr(spec, "powerset", False):
            raise ValueError(
                "PyanNetSegmenter requires a powerset model — check model.specifications.powerset"
            )
        self._num_classes = len(spec.classes)  # 3 local speakers
        self._powerset_max_classes = spec.powerset_max_classes  # 2
        self.powerset = Powerset(self._num_classes, self._powerset_max_classes).to(self.device)

        # frame-level sliding window for downstream count/reconstruct
        self._receptive_field = self._build_receptive_field()

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def num_local_speakers(self) -> int:
        return self._num_classes

    @property
    def receptive_field(self) -> SlidingWindow:
        return self._receptive_field

    def _build_receptive_field(self) -> SlidingWindow:
        """Frame resolution computed from PyanNet's SincNet receptive field."""
        sample_rate = self.model.sample_rate
        # frame center stride / sample-rate gives seconds-per-frame
        rf_size_samples = self.model.receptive_field_size(num_frames=1)
        rf_center_0 = self.model.receptive_field_center(frame=0)
        rf_center_1 = self.model.receptive_field_center(frame=1)
        frame_step = (rf_center_1 - rf_center_0) / sample_rate
        frame_duration = rf_size_samples / sample_rate
        frame_start = (rf_center_0 - 0.5 * (rf_size_samples - 1)) / sample_rate
        # Pyannote's Model.receptive_field uses (start, duration, step) — match it.
        return SlidingWindow(start=frame_start, duration=frame_duration, step=frame_step)

    @torch.inference_mode()
    def _forward_batch(self, batch: torch.Tensor) -> np.ndarray:
        """batch: (B, 1, samples) → multilabel (B, T, num_classes) numpy."""
        batch = batch.to(self.device)
        powerset_logits = self.model(batch)  # (B, T, num_powerset)
        multilabel = self.powerset.to_multilabel(powerset_logits, soft=False)
        return multilabel.cpu().numpy()

    def __call__(
        self, audio: Audio, hook: Callable[..., Any] | None = None
    ) -> SlidingWindowFeature:
        sample_rate = audio.sample_rate
        if sample_rate != self.model.sample_rate:
            raise ValueError(
                f"sample rate mismatch: audio={sample_rate}, model={self.model.sample_rate}"
            )

        waveform = audio.waveform  # (channels, samples)
        if waveform.dim() != 2:
            raise ValueError(f"expected (channels, samples) waveform, got {waveform.shape}")

        window_size = int(self._duration * sample_rate)
        step_size = round(self.step * sample_rate)
        _, num_samples = waveform.shape

        # full chunks via unfold
        if num_samples >= window_size:
            chunks = rearrange(
                waveform.unfold(1, window_size, step_size),
                "channel chunk frame -> chunk channel frame",
            )
            num_chunks = chunks.shape[0]
        else:
            chunks = waveform.new_zeros((0, waveform.shape[0], window_size))
            num_chunks = 0

        # last (partial) chunk → zero-pad
        has_last = (num_samples < window_size) or ((num_samples - window_size) % step_size > 0)
        last_chunk: torch.Tensor | None = None
        if has_last:
            tail = waveform[:, num_chunks * step_size :]
            pad = window_size - tail.shape[1]
            last_chunk = F.pad(tail, (0, pad))

        outputs: list[np.ndarray] = []
        total = num_chunks + (1 if has_last else 0)
        completed = 0
        if hook is not None:
            hook("segmentation", None, completed=0, total=total)

        for c in range(0, num_chunks, self.batch_size):
            batch = chunks[c : c + self.batch_size]
            outputs.append(self._forward_batch(batch))
            completed += batch.shape[0]
            if hook is not None:
                hook("segmentation", None, completed=completed, total=total)

        if last_chunk is not None:
            outputs.append(self._forward_batch(last_chunk[None]))
            completed += 1
            if hook is not None:
                hook("segmentation", None, completed=completed, total=total)

        stacked = np.vstack(outputs)  # (num_chunks_total, num_frames, num_classes)

        chunk_window = SlidingWindow(start=0.0, duration=self._duration, step=self.step)
        return SlidingWindowFeature(stacked, chunk_window)


def load_pyannet_segmenter(
    model_id: str = "pyannote/segmentation-3.0",
    duration: float = 10.0,
    step: float | None = None,
    batch_size: int = 32,
    device: torch.device | None = None,
    token: str | None = None,
    cache_dir: str | None = None,
) -> PyanNetSegmenter:
    """Convenience: bootstrap PyanNet weights and wrap in the adapter."""
    model = PyanNet.from_pyannote(model_id, token=token, cache_dir=cache_dir)
    return PyanNetSegmenter(
        model=model, duration=duration, step=step, batch_size=batch_size, device=device
    )
