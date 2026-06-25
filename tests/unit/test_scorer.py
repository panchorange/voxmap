"""SpeakerScorer implementations: cos baseline + AS-norm, and the registry seam."""

from __future__ import annotations

import numpy as np

from voxmap.registry import get_scorer
from voxmap.scorer.as_norm import ASNormScorer
from voxmap.scorer.cos import CosScorer


def _axis_vec(dim: int, axis: int, scale: float = 1.0) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float32)
    v[axis] = scale
    return v


def test_cos_centroid_identical_direction_scores_one() -> None:
    scorer = CosScorer(reduction="centroid")
    enroll = np.vstack([_axis_vec(8, 0), _axis_vec(8, 0, 2.0)])  # same direction
    assert scorer.score(_axis_vec(8, 0), enroll) > 0.999


def test_cos_orthogonal_scores_zero() -> None:
    scorer = CosScorer(reduction="centroid")
    assert abs(scorer.score(_axis_vec(8, 0), _axis_vec(8, 1)[None, :])) < 1e-5


def test_cos_max_reduction_picks_best_reference() -> None:
    scorer = CosScorer(reduction="max")
    # one reference matches the query, one is orthogonal: max should be ~1
    enroll = np.vstack([_axis_vec(8, 0), _axis_vec(8, 1)])
    assert scorer.score(_axis_vec(8, 0), enroll) > 0.999


def test_score_matrix_shape() -> None:
    scorer = CosScorer()
    queries = np.vstack([_axis_vec(8, 0), _axis_vec(8, 1)])  # (2, 8)
    gallery = [_axis_vec(8, 0)[None, :], _axis_vec(8, 1)[None, :], _axis_vec(8, 2)[None, :]]
    assert scorer.score_matrix(queries, gallery).shape == (2, 3)


def test_asnorm_separates_target_from_impostor() -> None:
    rng = np.random.default_rng(0)
    dim = 32
    cohort = rng.standard_normal((200, dim)).astype(np.float32)
    scorer = ASNormScorer(topk=50)
    scorer.fit(cohort)
    target = _axis_vec(dim, 0)
    enroll = np.vstack([target, _axis_vec(dim, 0, 1.5)])
    same = scorer.score(target, enroll)
    other = scorer.score(_axis_vec(dim, 1), enroll)
    assert same > other


def test_asnorm_requires_fit() -> None:
    scorer = ASNormScorer()
    try:
        scorer.score(_axis_vec(8, 0), _axis_vec(8, 0)[None, :])
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError before fit()")


def test_registry_resolves_scorers() -> None:
    assert isinstance(get_scorer("cos"), CosScorer)
    assert isinstance(get_scorer("as-norm"), ASNormScorer)
    try:
        get_scorer("nope")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown scorer")
