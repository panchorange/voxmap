"""Swappable speaker-similarity scoring.

`SpeakerScorer` is the one seam the recommender / suspicion logic talks to, so
the comparison method (raw cosine, AS-norm, PLDA, ...) can be swapped via
`registry.get_scorer` without touching callers. AS-norm is the default; cos is
the no-normalization baseline.
"""

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class SpeakerScorer(Protocol):
    def fit(self, cohort: NDArray[np.float32]) -> None:
        """Prepare any data-dependent state (e.g. cohort for AS-norm).

        No-op for scorers that need none (raw cosine).
        """
        ...

    def score(self, query: NDArray[np.float32], enroll: NDArray[np.float32]) -> float:
        """Similarity of a single `query` (D,) to one speaker's `enroll` (N, D).

        Higher means more likely the same speaker.
        """
        ...

    def score_matrix(
        self, queries: NDArray[np.float32], gallery: list[NDArray[np.float32]]
    ) -> NDArray[np.float32]:
        """Score `queries` (Q, D) against every speaker's enroll -> (Q, S).

        Eager batch path for the analysis/UI "suspicion map" (compute once).
        """
        ...
