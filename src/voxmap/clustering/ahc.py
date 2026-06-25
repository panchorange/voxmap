"""Agglomerative hierarchical clustering matching pyannote/speaker-diarization-3.1.

Uses scipy linkage + fcluster (NOT sklearn). centroid linkage with cosine metric
unit-normalizes embeddings first then runs euclidean linkage — same as upstream.

Hyperparameters from speaker-diarization-3.1 config:
  threshold = 0.7045654963945799
  method    = "centroid"
  min_cluster_size = 12

Inputs:
  embeddings: (num_chunks, num_local_speakers, dim)
  segmentations: (num_chunks, num_frames, num_local_speakers) binary

Outputs (matches pyannote BaseClustering.__call__):
  hard_clusters: (num_chunks, num_local_speakers) int — global speaker id, or -2 inactive
  soft_clusters: (num_chunks, num_local_speakers, num_clusters) float
  centroids: (num_clusters, dim) float

The flow:
  1. filter_embeddings  — drop NaN / inactive (single_active_ratio < 0.2)
  2. cluster            — scipy linkage + fcluster, then small-cluster reassignment
  3. assign_embeddings  — broadcast cluster ids back to all (chunk, speaker) pairs
"""

from __future__ import annotations

import numpy as np
from einops import rearrange
from pyannote.core import SlidingWindowFeature
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import cdist


class AHC:
    """Agglomerative hierarchical clustering — pyannote-3.1 compatible."""

    def __init__(
        self,
        threshold: float = 0.7045654963945799,
        method: str = "centroid",
        min_cluster_size: int = 12,
        metric: str = "cosine",
        min_cluster_fraction: float | None = None,
    ) -> None:
        self.threshold = threshold
        self.method = method
        self.min_cluster_size = min_cluster_size
        self.metric = metric
        # When set, the small-cluster floor scales with the embedding count:
        # max(2, round(min_cluster_fraction * n)) instead of the absolute
        # min_cluster_size. This adapts to per-speaker sample count, which varies
        # ~20x across datasets (AMI ~200 emb/speaker vs VoxConverse ~10) — a fixed
        # absolute floor either kills sparse speakers (VoxConverse under-count) or
        # under-filters (AMI over-split). See analysis/2026-05-21_mcs-threshold-joint-sweep.
        self.min_cluster_fraction = min_cluster_fraction

    @staticmethod
    def _filter_embeddings(
        embeddings: np.ndarray,
        segmentations: SlidingWindowFeature,
        min_active_ratio: float = 0.2,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        _, num_frames, _ = segmentations.data.shape
        single_active = np.sum(segmentations.data, axis=2, keepdims=True) == 1
        num_clean = np.sum(segmentations.data * single_active, axis=1)
        active = num_clean >= min_active_ratio * num_frames
        valid = ~np.any(np.isnan(embeddings), axis=2)
        chunk_idx, speaker_idx = np.where(active * valid)
        return embeddings[chunk_idx, speaker_idx], chunk_idx, speaker_idx

    @staticmethod
    def compute_linkage(
        embeddings: np.ndarray,
        method: str = "centroid",
        metric: str = "cosine",
    ) -> np.ndarray:
        """scipy linkage matrix Z — the exact tree `_cluster` cuts.

        For cosine + centroid/median/ward the embeddings are L2-normalized then
        linked with the euclidean metric (upstream pyannote-3.1 behavior). Exposed
        as a single source of truth so analysis/visualization can draw the *same*
        dendrogram the pipeline cut, without re-deriving the normalization.
        """
        if metric == "cosine" and method in ("centroid", "median", "ward"):
            with np.errstate(divide="ignore", invalid="ignore"):
                emb_normed = embeddings / np.linalg.norm(embeddings, axis=-1, keepdims=True)
            return np.asarray(linkage(emb_normed, method=method, metric="euclidean"))
        return np.asarray(linkage(embeddings, method=method, metric=metric))

    @staticmethod
    def _set_num_clusters(
        n: int,
        num_clusters: int | None,
        min_clusters: int | None,
        max_clusters: int | None,
    ) -> tuple[int | None, int, int]:
        min_c = num_clusters or min_clusters or 1
        min_c = max(1, min(n, min_c))
        max_c = num_clusters or max_clusters or n
        max_c = max(1, min(n, max_c))
        if min_c > max_c:
            raise ValueError(f"min_clusters > max_clusters ({min_c}, {max_c})")
        if min_c == max_c:
            num_clusters = min_c
        return num_clusters, min_c, max_c

    def _cluster(
        self,
        embeddings: np.ndarray,
        min_clusters: int,
        max_clusters: int,
        num_clusters: int | None,
    ) -> np.ndarray:
        n, _ = embeddings.shape
        if self.min_cluster_fraction is not None:
            min_cluster_size = max(2, round(self.min_cluster_fraction * n))
        else:
            min_cluster_size = min(self.min_cluster_size, max(1, round(0.1 * n)))

        if n == 1:
            return np.zeros((1,), dtype=np.uint8)

        dendrogram = self.compute_linkage(embeddings, method=self.method, metric=self.metric)

        clusters = fcluster(dendrogram, self.threshold, criterion="distance") - 1

        unique, counts = np.unique(clusters, return_counts=True)
        large_clusters = unique[counts >= min_cluster_size]
        num_large = len(large_clusters)

        if num_large < min_clusters:
            num_clusters = min_clusters
        elif num_large > max_clusters:
            num_clusters = max_clusters

        if num_clusters is not None and num_large != num_clusters:
            # navigate dendrogram by closest-iteration to the threshold
            _dend = dendrogram.copy()
            _dend[:, 2] = np.arange(n - 1)

            best_iter = n - 1
            best_num = 1
            for it in np.argsort(np.abs(dendrogram[:, 2] - self.threshold)):
                new_size = _dend[it, 3]
                if new_size < min_cluster_size:
                    continue
                clusters = fcluster(_dend, it, criterion="distance") - 1
                u, cnt = np.unique(clusters, return_counts=True)
                lc = u[cnt >= min_cluster_size]
                nl = len(lc)
                if abs(nl - num_clusters) < abs(best_num - num_clusters):
                    best_iter = it
                    best_num = nl
                if nl == num_clusters:
                    break
            if best_num != num_clusters:
                clusters = fcluster(_dend, best_iter, criterion="distance") - 1
                u, cnt = np.unique(clusters, return_counts=True)
                large_clusters = u[cnt >= min_cluster_size]
                num_large = len(large_clusters)

        clusters_arr: np.ndarray = clusters
        if num_large == 0:
            clusters_arr[:] = 0
            return clusters_arr

        unique, counts = np.unique(clusters_arr, return_counts=True)
        large_clusters = unique[counts >= min_cluster_size]
        small_clusters = unique[counts < min_cluster_size]
        if len(small_clusters) == 0:
            return clusters_arr

        # reassign each small cluster to the most similar large-cluster centroid
        large_centroids = np.vstack(
            [np.mean(embeddings[clusters == k], axis=0) for k in large_clusters]
        )
        small_centroids = np.vstack(
            [np.mean(embeddings[clusters == k], axis=0) for k in small_clusters]
        )
        dist = cdist(large_centroids, small_centroids, metric=self.metric)
        for small_k, large_k in enumerate(np.argmin(dist, axis=0)):
            clusters[clusters == small_clusters[small_k]] = large_clusters[large_k]

        # renumber 0 .. num_large_clusters-1
        _, clusters = np.unique(clusters, return_inverse=True)
        return clusters

    def _assign_embeddings(
        self,
        embeddings: np.ndarray,
        train_chunk_idx: np.ndarray,
        train_speaker_idx: np.ndarray,
        train_clusters: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        num_clusters = int(np.max(train_clusters)) + 1
        num_chunks, num_speakers, _ = embeddings.shape
        train_emb = embeddings[train_chunk_idx, train_speaker_idx]
        centroids = np.vstack(
            [np.mean(train_emb[train_clusters == k], axis=0) for k in range(num_clusters)]
        )

        e2k = rearrange(
            cdist(rearrange(embeddings, "c s d -> (c s) d"), centroids, metric=self.metric),
            "(c s) k -> c s k",
            c=num_chunks,
            s=num_speakers,
        )
        soft = 2 - e2k
        hard = np.argmax(soft, axis=2)
        return hard, soft, centroids

    def __call__(
        self,
        embeddings: np.ndarray,
        segmentations: SlidingWindowFeature,
        num_clusters: int | None = None,
        min_clusters: int | None = None,
        max_clusters: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        train_emb, train_chunk_idx, train_speaker_idx = self._filter_embeddings(
            embeddings, segmentations
        )
        n = train_emb.shape[0]
        num_clusters, min_c, max_c = self._set_num_clusters(
            n, num_clusters=num_clusters, min_clusters=min_clusters, max_clusters=max_clusters
        )
        if max_c < 2:
            num_chunks, num_speakers, _ = embeddings.shape
            hard = np.zeros((num_chunks, num_speakers), dtype=np.int8)
            soft = np.ones((num_chunks, num_speakers, 1))
            centroids = np.mean(train_emb, axis=0, keepdims=True)
            return hard, soft, centroids

        train_clusters = self._cluster(
            train_emb, min_clusters=min_c, max_clusters=max_c, num_clusters=num_clusters
        )
        return self._assign_embeddings(
            embeddings, train_chunk_idx, train_speaker_idx, train_clusters
        )
