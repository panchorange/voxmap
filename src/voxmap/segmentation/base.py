"""Segmenter Protocol.

A Segmenter takes audio and returns chunk-level multilabel speaker activations
as a `pyannote.core.SlidingWindowFeature`. This shape is shared by the
downstream embedding adapter and pipeline orchestrator.
"""

from __future__ import annotations

from typing import Protocol

from pyannote.core import SlidingWindowFeature

from voxmap.types import Audio


class Segmenter(Protocol):
    """Chunk-based powerset segmenter.

    Returns
    -------
    segmentations : SlidingWindowFeature
        Data shape (num_chunks, num_frames, num_local_speakers).
        Multilabel (binary) activations after powerset → multilabel conversion.
        sliding_window: chunk timing (start=0, duration, step).
    receptive_field : SlidingWindow
        Frame-level resolution (used by speaker_count and reconstruct).
    duration : float
        Chunk duration in seconds.
    """

    def __call__(self, audio: Audio) -> SlidingWindowFeature: ...

    @property
    def duration(self) -> float: ...

    @property
    def receptive_field(self) -> object: ...  # pyannote.core.SlidingWindow
