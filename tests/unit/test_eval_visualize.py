"""Unit tests for voxmap.eval.visualize pure helpers + AHC.compute_linkage.

These avoid the heavy pipeline (no model/audio): they exercise the metric and
parsing helpers, and verify the linkage helper reproduces the cut AHC._cluster
makes internally.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.cluster.hierarchy import fcluster

from voxmap.clustering.ahc import AHC
from voxmap.eval.visualize import annot_segments, cluster_metrics
from voxmap.types import Diarization, Segment, SpeakerTurn


def test_cluster_metrics_purity_and_count_error() -> None:
    seg_labels = np.array([0, 0, 0, 1, 1])
    ref_labels = np.array(["A", "A", "B", "B", "B"])
    m = cluster_metrics(seg_labels, ref_labels, n_pred=2, n_ref=3)
    # cluster 0 majority A (2/3), cluster 1 majority B (2/2) -> (2+2)/5
    assert m["cluster_purity"] == pytest.approx(0.8)
    assert m["n_segments"] == 5
    assert m["count_error"] == -1  # 2 - 3
    assert m["n_speakers_pred"] == 2
    assert m["n_speakers_ref"] == 3
    assert m["n_clusters"] == 2  # unique seg_labels {0, 1}


def test_cluster_metrics_empty() -> None:
    m = cluster_metrics(np.array([]), np.array([]), n_pred=0, n_ref=0)
    assert m["cluster_purity"] == 0.0
    assert m["n_segments"] == 0
    assert m["n_clusters"] == 0


def test_annot_segments_from_diarization() -> None:
    diar = Diarization(
        turns=[
            SpeakerTurn(segment=Segment(0.0, 1.5), speaker="spk0"),
            SpeakerTurn(segment=Segment(2.0, 3.0), speaker="spk1"),
        ]
    )
    segs = annot_segments(diar)
    assert segs == [("spk0", 0.0, 1.5), ("spk1", 2.0, 3.0)]


def test_compute_linkage_shape_and_determinism() -> None:
    rng = np.random.default_rng(0)
    emb = rng.standard_normal((6, 8)).astype(np.float32)
    z1 = AHC.compute_linkage(emb, method="centroid", metric="cosine")
    z2 = AHC.compute_linkage(emb, method="centroid", metric="cosine")
    assert z1.shape == (5, 4)  # (n-1, 4)
    assert np.allclose(z1, z2)
    assert np.isfinite(z1).all()


def test_compute_linkage_reproduces_internal_cut() -> None:
    """fcluster on compute_linkage(emb) == labels AHC._cluster computes internally."""
    rng = np.random.default_rng(1)
    # two well-separated blobs so clustering is unambiguous
    emb = np.vstack(
        [rng.standard_normal((8, 16)) + 5.0, rng.standard_normal((8, 16)) - 5.0]
    ).astype(np.float32)
    ahc = AHC()
    z = AHC.compute_linkage(emb, method=ahc.method, metric=ahc.metric)
    raw = fcluster(z, ahc.threshold, criterion="distance") - 1
    # _cluster applies small-cluster merge on top, but with 8+8 points and
    # min_cluster_size capped at round(0.1*16)=2, both blobs survive as clusters.
    labels = ahc._cluster(emb, min_clusters=1, max_clusters=16, num_clusters=None)
    assert len(np.unique(raw)) == 2
    assert len(np.unique(labels)) == 2
