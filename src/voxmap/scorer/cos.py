"""Raw cosine scorer — the no-normalization baseline `SpeakerScorer`."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from voxmap.linalg import cosine_similarity, l2_normalize


class CosScorer:
    """Cosine similarity with no cohort normalization.

    reduction — how to collapse a speaker's multiple enroll vectors into a score:
      "centroid" : cos(query, normalized mean(enroll))  — standard ASV averaging (default)
      "max"      : max_i cos(query, enroll_i)            — robust to within-speaker spread
    """

    def __init__(self, reduction: str = "centroid") -> None:
        if reduction not in ("centroid", "max"):
            raise ValueError(f"Unknown reduction: {reduction!r}")
        self.reduction = reduction

    def fit(self, cohort: NDArray[np.float32]) -> None:
        return None  # raw cosine needs no cohort

    def score(self, query: NDArray[np.float32], enroll: NDArray[np.float32]) -> float:
        q = np.atleast_2d(query)
        enroll = np.atleast_2d(enroll)
        if self.reduction == "centroid":
            centroid = l2_normalize(enroll.mean(axis=0, keepdims=True))
            return float(cosine_similarity(q, centroid)[0, 0])
        return float(cosine_similarity(q, enroll).max())

    def score_matrix(
        self, queries: NDArray[np.float32], gallery: list[NDArray[np.float32]]
    ) -> NDArray[np.float32]:
        queries = np.atleast_2d(queries)
        return np.asarray(
            [[self.score(q, enroll) for enroll in gallery] for q in queries],
            dtype=np.float32,
        )
