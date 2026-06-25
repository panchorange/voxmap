"""AHC.min_cluster_fraction: the small-cluster floor scales with embedding count.

Regression for analysis/2026-05-21_mcs-threshold-joint-sweep: a fixed absolute
min_cluster_size merges away small (sparse) speakers; a fractional floor keeps
them when they clear round(fraction * n).
"""

from __future__ import annotations

import numpy as np

from voxmap.clustering.ahc import AHC


def _three_blobs() -> np.ndarray:
    """Two large blobs (40 each) + one small blob (3), mutually distant directions."""
    rng = np.random.default_rng(2)
    dim = 16
    big1 = np.zeros((40, dim))
    big1[:, 0] = 10.0
    big2 = np.zeros((40, dim))
    big2[:, 1] = 10.0
    small = np.zeros((3, dim))
    small[:, 2] = 10.0
    emb = np.vstack([big1, big2, small]).astype(np.float32)
    emb += rng.standard_normal(emb.shape).astype(np.float32) * 0.05  # tight within-blob
    return emb


def test_absolute_floor_merges_small_cluster() -> None:
    """Default min_cluster_size=12 drops the 3-point blob -> 2 clusters."""
    emb = _three_blobs()  # n = 83
    labels = AHC()._cluster(emb, min_clusters=1, max_clusters=83, num_clusters=None)
    assert len(np.unique(labels)) == 2


def test_fraction_floor_keeps_small_cluster() -> None:
    """fraction 0.02 -> floor max(2, round(0.02*83)) = 2; the 3-point blob survives -> 3."""
    emb = _three_blobs()
    labels = AHC(min_cluster_fraction=0.02)._cluster(
        emb, min_clusters=1, max_clusters=83, num_clusters=None
    )
    assert len(np.unique(labels)) == 3
