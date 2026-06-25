"""Adaptive symmetric score normalization (AS-norm) `SpeakerScorer`.

The default scorer. Raw cosine thresholds drift per speaker; AS-norm rescales a
score by each side's similarity distribution against an impostor cohort, so a
single global threshold tau becomes meaningful across speakers (and across the
open-set "novel speaker" rejection).

Enrollment is represented by its (normalized) centroid — AS-norm operates on a
single enroll vector vs a single query.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from voxmap.linalg import cosine_similarity, l2_normalize


class ASNormScorer:
    """AS-norm over cosine, normalized against a top-k impostor cohort.

    topk  — cohort size used for the per-side mean/std (adaptive cohort).
    eps   — std floor to avoid divide-by-zero on degenerate cohorts.
    """

    def __init__(self, topk: int = 300, eps: float = 1e-6) -> None:
        self.topk = topk
        self.eps = eps
        self._cohort: NDArray[np.float32] | None = None  # (C, D), L2-normalized

    def fit(self, cohort: NDArray[np.float32]) -> None:
        self._cohort = l2_normalize(np.atleast_2d(cohort))

    def _side_stats(self, vec: NDArray[np.float32]) -> tuple[float, float]:
        """mean/std of the top-k cohort cosine scores for one (1, D) vector."""
        assert self._cohort is not None
        sims = cosine_similarity(vec, self._cohort)[0]  # (C,)
        k = min(self.topk, sims.shape[0])
        top = np.sort(sims)[-k:]
        return float(top.mean()), float(top.std())

    def score(self, query: NDArray[np.float32], enroll: NDArray[np.float32]) -> float:
        if self._cohort is None:
            raise RuntimeError("ASNormScorer.fit(cohort) must be called before score()")
        q = l2_normalize(np.atleast_2d(query))
        e = l2_normalize(np.atleast_2d(enroll).mean(axis=0, keepdims=True))
        s = float(cosine_similarity(q, e)[0, 0])
        mean_e, std_e = self._side_stats(e)
        mean_q, std_q = self._side_stats(q)
        z_e = (s - mean_e) / (std_e + self.eps)
        z_q = (s - mean_q) / (std_q + self.eps)
        return 0.5 * (z_e + z_q)

    def score_matrix(
        self, queries: NDArray[np.float32], gallery: list[NDArray[np.float32]]
    ) -> NDArray[np.float32]:
        queries = np.atleast_2d(queries)
        return np.asarray(
            [[self.score(q, enroll) for enroll in gallery] for q in queries],
            dtype=np.float32,
        )
