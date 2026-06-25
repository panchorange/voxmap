"""Value types for speaker recommendation (open-set ASV over an enrolled gallery)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candidate:
    """One known speaker scored against a query, higher score = more likely."""

    speaker: str
    score: float


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Top-k known-speaker candidates for one query segment.

    `is_novel` is the open-set rejection verdict: the best candidate fell below
    tau, so "new speaker" is the recommended action.
    """

    candidates: list[Candidate]
    is_novel: bool

    @property
    def top(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None

    @property
    def margin(self) -> float:
        """top1 - top2 score gap. inf if fewer than two candidates."""
        if len(self.candidates) < 2:
            return float("inf")
        return self.candidates[0].score - self.candidates[1].score


@dataclass(frozen=True, slots=True)
class ClusterMapping:
    """Proposed mapping of one auto-diarization cluster to a known speaker.

    `speaker is None` means no known speaker cleared tau -> treat as novel.
    """

    cluster: str
    speaker: str | None
    score: float


@dataclass(frozen=True, slots=True)
class MappingProposal:
    """The batch cluster->speaker proposal shown in the confirmation popup."""

    mappings: list[ClusterMapping]
