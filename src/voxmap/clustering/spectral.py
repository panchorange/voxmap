"""NME-SC spectral clustering — drop-in for AHC in the speaker-diarization-3.1 stack.

AHC cuts a dendrogram at a fixed cosine threshold, which collapses to one speaker
when CAM++ embeddings share a high baseline similarity (in-the-wild many-talker
audio). Spectral clustering instead projects the affinity graph into its Laplacian
eigenspace and picks the speaker count from the maximum eigengap (NME-SC, Park et
al. 2019), which is robust to that regime.

Two findings from analysis/2026-05-22_msdwild-spectral-poc drive the design:
  - **recording-mean centering** is required: raw CAM++ cosine affinity is washed
    out (mean ~0.84, blocks invisible); subtracting the per-recording mean exposes
    the speaker blocks (mean ~0.50) and lifts cluster purity 0.67 -> 0.86.
  - NME-SC over-splits, so `max_clusters` caps the speaker count.

Subclasses `AHC` to reuse its filter / num-cluster / assign plumbing; only the core
`_cluster` step (dendrogram cut) is replaced by NME-SC on the centered embeddings.
"""

from __future__ import annotations

import numpy as np

from voxmap.clustering.ahc import AHC


class SpectralClustering(AHC):
    """NME-SC spectral clustering with recording-mean centering."""

    def __init__(
        self,
        center: bool = True,
        max_clusters: int = 15,
        p_percentile_min: float = 0.40,
        p_percentile_max: float = 0.95,
        **ahc_kwargs: object,
    ) -> None:
        super().__init__(**ahc_kwargs)  # type: ignore[arg-type]
        self.center = center
        self.spectral_max_clusters = max_clusters
        self.p_percentile_min = p_percentile_min
        self.p_percentile_max = p_percentile_max

    def _cluster(
        self,
        embeddings: np.ndarray,
        min_clusters: int,
        max_clusters: int,
        num_clusters: int | None,
    ) -> np.ndarray:
        n, _ = embeddings.shape
        if n == 1:
            return np.zeros((1,), dtype=np.int64)

        emb = embeddings - embeddings.mean(axis=0, keepdims=True) if self.center else embeddings

        from spectralcluster import (
            AutoTune,
            RefinementName,
            RefinementOptions,
            SpectralClusterer,
            ThresholdType,
        )

        refinement = RefinementOptions(
            gaussian_blur_sigma=0,
            p_percentile=0.95,
            thresholding_soft_multiplier=0.01,
            thresholding_type=ThresholdType.RowMax,
            refinement_sequence=[RefinementName.RowWiseThreshold, RefinementName.Symmetrize],
        )
        autotune = AutoTune(
            p_percentile_min=self.p_percentile_min,
            p_percentile_max=self.p_percentile_max,
            init_search_step=0.02,
            search_level=3,
        )
        # cap the speaker count: NME-SC over-splits, and downstream max_speakers
        # (if the caller set one) should still bound it.
        max_c = num_clusters or max_clusters or self.spectral_max_clusters
        max_c = max(1, min(self.spectral_max_clusters, int(max_c), n))
        min_c = max(1, min(num_clusters or min_clusters or 1, max_c))

        clusterer = SpectralClusterer(
            min_clusters=min_c,
            max_clusters=max_c,
            refinement_options=refinement,
            autotune=autotune,
        )
        labels = np.asarray(clusterer.predict(emb))
        # renumber to a contiguous 0..k-1 range (AHC._assign_embeddings expects this)
        _, labels = np.unique(labels, return_inverse=True)
        return labels.astype(np.int64)
