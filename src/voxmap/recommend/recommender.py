"""Enrollment-based speaker recommendation (open-set ASV).

Two entry points mirroring the annotation flow:
  - `propose_mapping` : batch cluster->speaker proposal for the post-diarization
    confirmation popup (one-to-one optimal assignment, Hungarian).
  - `recommend`       : per-segment top-k candidates for the "R" action, with
    open-set rejection (novel speaker) below tau.

Scorer-agnostic: all comparisons go through an injected `SpeakerScorer`.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment

from voxmap.recommend.enrollment import Gallery
from voxmap.recommend.types import (
    Candidate,
    ClusterMapping,
    MappingProposal,
    Recommendation,
)
from voxmap.scorer.base import SpeakerScorer


class Recommender:
    def __init__(
        self,
        scorer: SpeakerScorer,
        gallery: Gallery,
        threshold: float,
        top_k: int = 3,
    ) -> None:
        self.scorer = scorer
        self.gallery = gallery
        self.threshold = threshold
        self.top_k = top_k

    def recommend(self, query: NDArray[np.float32]) -> Recommendation:
        """Top-k known speakers for one query embedding; novel if best < tau."""
        names = self.gallery.names()
        if not names:
            return Recommendation(candidates=[], is_novel=True)
        scores = self.scorer.score_matrix(np.atleast_2d(query), self.gallery.as_list(names))[0]
        order = np.argsort(scores)[::-1]
        candidates = [Candidate(names[int(j)], float(scores[int(j)])) for j in order[: self.top_k]]
        best = float(scores[int(order[0])])
        return Recommendation(candidates=candidates, is_novel=best < self.threshold)

    def propose_mapping(self, clusters: dict[str, NDArray[np.float32]]) -> MappingProposal:
        """Optimal one-to-one cluster->speaker mapping; below-tau clusters stay novel."""
        cluster_ids = list(clusters.keys())
        names = self.gallery.names()
        if not names or not cluster_ids:
            return MappingProposal([ClusterMapping(c, None, float("-inf")) for c in cluster_ids])

        queries = np.vstack([np.atleast_2d(clusters[c]).mean(axis=0) for c in cluster_ids]).astype(
            np.float32
        )
        score_mat = self.scorer.score_matrix(queries, self.gallery.as_list(names))  # (C, S)
        row_ind, col_ind = linear_sum_assignment(-score_mat)
        assigned = {int(r): int(c) for r, c in zip(row_ind, col_ind, strict=True)}

        mappings: list[ClusterMapping] = []
        for i, cluster in enumerate(cluster_ids):
            if i not in assigned:  # more clusters than known speakers -> novel
                mappings.append(ClusterMapping(cluster, None, float("-inf")))
                continue
            j = assigned[i]
            score = float(score_mat[i, j])
            speaker = names[j] if score >= self.threshold else None
            mappings.append(ClusterMapping(cluster, speaker, score))
        return MappingProposal(mappings)
