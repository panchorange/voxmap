"""Voxmap re-implementation of pyannote/speaker-diarization-3.1 apply() flow.

This pipeline orchestrates the 5 stages identified in the stage profiling
experiment ([[../../docs/research/pyannote-3.1_アーキテクチャと時間プロファイル]]):

  1. segmentation        — PyanNetSegmenter
  2. speaker_counting    — frame-level instantaneous active count (numpy)
  3. embeddings          — WeSpeakerEmbedder (chunk × local_speaker → 256-dim)
  4. clustering          — AHC (scipy centroid linkage)
  5. finalize            — reconstruct + to_annotation + label rename

For Phase 2-1 we still import a few small pyannote utilities for parity:
  - speaker_count / to_annotation / to_diarization (SpeakerDiarizationMixin)
  - Binarize (used inside to_annotation)
These are pure numpy/SlidingWindowFeature helpers, not heavy compute.
They are candidates for a Phase 2-2 vendor pass.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

import numpy as np
import torch
from pyannote.audio.pipelines.utils.diarization import SpeakerDiarizationMixin
from pyannote.core import Annotation, SlidingWindowFeature

from voxmap.clustering.ahc import AHC
from voxmap.embedding.wespeaker_emb import (
    WeSpeakerEmbedder,
    load_campplus_embedder,
    load_wespeaker_embedder,
)
from voxmap.segmentation.pyannet_seg import PyanNetSegmenter, load_pyannet_segmenter
from voxmap.types import Audio


def _reconstruct(
    segmentations: SlidingWindowFeature,
    hard_clusters: np.ndarray,
    count: SlidingWindowFeature,
    mixin: SpeakerDiarizationMixin,
) -> SlidingWindowFeature:
    """chunk×local_speaker masked segmentations → frame×global_speaker."""
    num_chunks, num_frames, _ = segmentations.data.shape
    num_clusters = int(np.max(hard_clusters)) + 1
    clustered = np.full((num_chunks, num_frames, num_clusters), np.nan, dtype=np.float32)

    for c, cluster in enumerate(hard_clusters):
        # segmentation: (num_frames, num_local_speakers) for this chunk
        segmentation = segmentations.data[c]
        for k in np.unique(cluster):
            if k == -2:
                continue
            clustered[c, :, k] = np.max(segmentation[:, cluster == k], axis=1)

    swf = SlidingWindowFeature(clustered, segmentations.sliding_window)
    return mixin.to_diarization(swf, count)


def _validate_min_duration_on(value: float) -> None:
    """0.0 (無効化) または [0.1, 1.0] のみ許可する。"""
    if value != 0.0 and not (0.1 <= value <= 1.0):
        raise ValueError(f"min_duration_on must be 0.0 (disabled) or in [0.1, 1.0], got {value!r}")


class Diarization31Pipeline:
    """Self-implemented voxmap version of pyannote/speaker-diarization-3.1.

    Parameters mirror the upstream pipeline so that DER parity is testable
    against `2026-05-07_pyannote4_pretrained_baseline`.
    """

    def __init__(
        self,
        segmenter: PyanNetSegmenter,
        embedder: WeSpeakerEmbedder,
        clustering: AHC,
        min_duration_off: float = 0.0,
        min_duration_on: float = 0.3,
    ) -> None:
        _validate_min_duration_on(min_duration_on)
        self.segmenter = segmenter
        self.embedder = embedder
        self.clustering = clustering
        self.min_duration_off = min_duration_off
        self.min_duration_on = min_duration_on
        self._mixin = SpeakerDiarizationMixin()

    def __call__(
        self,
        audio: Audio,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        min_duration_on: float | None = None,
        uri: str = "audio",
        hook: Callable[..., Any] | None = None,
    ) -> Annotation:
        """Run full diarization. Returns a pyannote.core.Annotation.

        min_duration_on: per-call override of the constructor default (see
        __init__). Must be 0.0 (disabled) or in [0.1, 1.0] when given; None
        uses the instance default (self.min_duration_on).
        """
        effective_min_duration_on = (
            self.min_duration_on if min_duration_on is None else min_duration_on
        )
        _validate_min_duration_on(effective_min_duration_on)

        num_speakers, min_speakers, max_speakers = self._mixin.set_num_speakers(
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        # ① segmentation
        segmentations = self.segmenter(audio, hook=hook if hook else None)
        if hook is not None:
            hook("segmentation", segmentations)

        # 3.1 powerset path: binarized = segmentations as-is
        binarized = segmentations

        # ② speaker counting
        count = self._mixin.speaker_count(
            binarized,
            self.segmenter.receptive_field,
            warm_up=(0.0, 0.0),
        )
        if hook is not None:
            hook("speaker_counting", count)

        if np.nanmax(count.data) == 0.0:
            return Annotation(uri=uri)

        # ③ embeddings
        embeddings = self.embedder(audio, binarized, hook=hook)
        if hook is not None:
            hook("embeddings", embeddings)

        # ④ clustering
        hard_clusters, _, _centroids = self.clustering(
            embeddings,
            segmentations=binarized,
            num_clusters=num_speakers,
            min_clusters=min_speakers,
            max_clusters=max_speakers,
        )

        # cap instantaneous count by max_speakers (handle inf)
        cap = max_speakers if np.isfinite(max_speakers) else int(np.max(count.data))
        count.data = np.minimum(count.data, cap).astype(np.int8)

        # mark inactive speaker slots so reconstruct ignores them
        inactive = np.sum(binarized.data, axis=1) == 0
        hard_clusters[inactive] = -2
        if hook is not None:
            hook("hard_clusters", hard_clusters)

        # ⑤ reconstruct + to_annotation
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            discrete = _reconstruct(segmentations, hard_clusters, count, self._mixin)

        diarization = self._mixin.to_annotation(
            discrete,
            min_duration_on=effective_min_duration_on,
            min_duration_off=self.min_duration_off,
        )
        diarization.uri = uri

        # rename integer labels → SPEAKER_00, SPEAKER_01, ...
        mapping = {label: f"SPEAKER_{i:02d}" for i, label in enumerate(diarization.labels())}

        # Expose the global-cluster-id → SPEAKER_xx mapping. `hard_clusters` holds the
        # integer global ids; `centroids` is keyed by SPEAKER_xx. Callers that want to
        # gather a segment's constituent (chunk, local_speaker) embeddings (studio
        # suspicion map) need this to bridge the two id systems.
        if hook is not None:
            hook("label_mapping", {int(k): v for k, v in mapping.items()})

        # Expose per-cluster centroids keyed by the final SPEAKER_xx label so callers
        # (e.g. studio recommend) can match clusters to a known-speaker gallery WITHOUT
        # a second embedding pass. `label` is the AHC cluster id, which indexes
        # `_centroids` directly. Centroids are raw means (not L2-normalized).
        if hook is not None:
            centroids_by_label = {
                mapping[label]: _centroids[label] for label in diarization.labels()
            }
            hook("centroids", centroids_by_label)

        return diarization.rename_labels(mapping=mapping)


def load_diarization31_pipeline(
    segmentation_model: str = "pyannote/segmentation-3.0",
    embedding_model: str = "pyannote/wespeaker-voxceleb-resnet34-LM",
    threshold: float = 0.7045654963945799,
    method: str = "centroid",
    min_cluster_size: int = 12,
    min_cluster_fraction: float | None = None,
    clustering: str = "ahc",
    embedding_batch_size: int = 32,
    segmentation_batch_size: int = 32,
    embedding_exclude_overlap: bool = True,
    min_duration_off: float = 0.0,
    min_duration_on: float = 0.3,
    segmentation_step: float | None = None,
    embedding_per_chunk: bool = False,
    embedding_dtype: str = "float32",
    fbank_backend: str = "kaldi",
    device: torch.device | None = None,
    token: str | None = None,
    cache_dir: str | None = None,
) -> Diarization31Pipeline:
    """Convenience: load the full speaker-diarization-3.1 stack into voxmap.

    min_duration_on: drop hypothesis segments shorter than this (seconds).
        Suppresses isolated short false-alarm fragments at the cost of a
        (smaller) increase in missed detection. Must be 0.0 (disabled) or in
        [0.1, 1.0]; default 0.3 is a conservative balance between DER gain and
        the precision of what gets removed.
    segmentation_step: sliding-window step in seconds. None → 10% of chunk
        duration (pyannote default = 1.0s for 10s chunks). Larger values
        reduce chunk count (and embedding calls) at the cost of resolution.
    embedding_per_chunk: SpeakerKit-style per-chunk strategy. Encoder is run
        once per chunk and pooled with each local-speaker mask separately
        (instead of full forward per (chunk × speaker)). Currently CAM++ only.
    embedding_dtype: "float16" halves the embedding body for RTF (DER unchanged).
    fbank_backend: "melspec" replaces the kaldi fbank (CPU-fallback FFT on MPS)
        with torchaudio MelSpectrogram (MPS/CUDA native). CAM++ only.
        Together these reproduce the paper's proposed fast recipe.
    """
    segmenter = load_pyannet_segmenter(
        model_id=segmentation_model,
        step=segmentation_step,
        batch_size=segmentation_batch_size,
        device=device,
        token=token,
        cache_dir=cache_dir,
    )
    # dispatch by repo id prefix: WeSpeaker/* → CAM++, pyannote/* → ResNet34
    if embedding_model.startswith("Wespeaker/"):
        embedder = load_campplus_embedder(
            model_id=embedding_model,
            batch_size=embedding_batch_size,
            exclude_overlap=embedding_exclude_overlap,
            device=device,
            token=token,
            cache_dir=cache_dir,
            per_chunk=embedding_per_chunk,
        )
    else:
        embedder = load_wespeaker_embedder(
            model_id=embedding_model,
            batch_size=embedding_batch_size,
            exclude_overlap=embedding_exclude_overlap,
            device=device,
            token=token,
            cache_dir=cache_dir,
            per_chunk=embedding_per_chunk,
        )
    clusterer: AHC
    if clustering == "spectral":
        from voxmap.clustering.spectral import SpectralClustering

        clusterer = SpectralClustering(
            threshold=threshold,
            method=method,
            min_cluster_size=min_cluster_size,
            min_cluster_fraction=min_cluster_fraction,
        )
    elif clustering == "ahc":
        clusterer = AHC(
            threshold=threshold,
            method=method,
            min_cluster_size=min_cluster_size,
            min_cluster_fraction=min_cluster_fraction,
        )
    else:
        raise ValueError(f"unknown clustering {clustering!r} (use 'ahc' or 'spectral')")

    # RTF 最適化 (論文 proposed)。fp16 → melspec の順で適用 (melspec が fp16 前提)。
    if embedding_dtype == "float16":
        from voxmap.embedding.optimize import apply_embedding_fp16

        apply_embedding_fp16(embedder)
    if fbank_backend == "melspec":
        from voxmap.embedding.optimize import apply_melspec_fbank

        apply_melspec_fbank(embedder)

    return Diarization31Pipeline(
        segmenter=segmenter,
        embedder=embedder,
        clustering=clusterer,
        min_duration_off=min_duration_off,
        min_duration_on=min_duration_on,
    )
