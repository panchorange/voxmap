"""Gallery enrollment + Recommender (top-k, open-set rejection, batch cluster mapping)."""

from __future__ import annotations

import numpy as np

from voxmap.recommend.enrollment import Gallery
from voxmap.recommend.recommender import Recommender
from voxmap.scorer.cos import CosScorer


def _axis(dim: int, axis: int) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float32)
    v[axis] = 1.0
    return v


def _gallery() -> Gallery:
    g = Gallery()
    g.add("yamada", _axis(8, 0))
    g.add("tanaka", _axis(8, 1))
    return g


def test_gallery_add_append_and_save_load(tmp_path) -> None:
    g = Gallery()
    g.add("yamada", _axis(8, 0))
    g.add("yamada", np.vstack([_axis(8, 0), _axis(8, 0)]))  # append (N, D)
    assert g.vectors("yamada").shape == (3, 8)
    assert "tanaka" not in g
    g.save(tmp_path)
    reloaded = Gallery.load(tmp_path)
    assert reloaded.names() == ["yamada"]
    assert np.allclose(reloaded.vectors("yamada"), g.vectors("yamada"))


def test_recommend_orders_and_accepts_known() -> None:
    rec = Recommender(CosScorer(), _gallery(), threshold=0.5, top_k=2)
    out = rec.recommend(_axis(8, 0))  # clearly yamada
    assert out.top is not None and out.top.speaker == "yamada"
    assert out.is_novel is False
    assert out.candidates[0].score >= out.candidates[1].score


def test_recommend_rejects_novel_below_threshold() -> None:
    rec = Recommender(CosScorer(), _gallery(), threshold=0.5)
    out = rec.recommend(_axis(8, 5))  # orthogonal to everyone -> score ~0 < 0.5
    assert out.is_novel is True


def test_recommend_empty_gallery_is_novel() -> None:
    rec = Recommender(CosScorer(), Gallery(), threshold=0.5)
    out = rec.recommend(_axis(8, 0))
    assert out.is_novel is True and out.candidates == []


def test_propose_mapping_one_to_one() -> None:
    rec = Recommender(CosScorer(), _gallery(), threshold=0.5)
    clusters = {"speaker_00": _axis(8, 1)[None, :], "speaker_01": _axis(8, 0)[None, :]}
    proposal = rec.propose_mapping(clusters)
    by_cluster = {m.cluster: m.speaker for m in proposal.mappings}
    assert by_cluster == {"speaker_00": "tanaka", "speaker_01": "yamada"}


def test_propose_mapping_novel_cluster_below_threshold() -> None:
    rec = Recommender(CosScorer(), _gallery(), threshold=0.5)
    clusters = {"speaker_00": _axis(8, 6)[None, :]}  # matches no one
    proposal = rec.propose_mapping(clusters)
    assert proposal.mappings[0].speaker is None
