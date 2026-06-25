"""Speaker gallery: the enrolled reference vectors that recommendation scores against.

Holds, per known speaker, the multiple reference embeddings a human has confirmed
(multi-reference, not a single centroid — robust to within-speaker variance).
Persisted as one .npy per speaker so a session can resume and so cross-meeting
enrollment can be reused.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray


class Gallery:
    """Mutable map of speaker name -> (N, D) reference embeddings."""

    def __init__(self) -> None:
        self._enroll: dict[str, NDArray[np.float32]] = {}

    def add(self, speaker: str, vectors: NDArray[np.float32]) -> None:
        """Append reference vector(s) for a speaker. `vectors` is (D,) or (N, D)."""
        vecs = np.atleast_2d(np.asarray(vectors, dtype=np.float32))
        if speaker in self._enroll:
            self._enroll[speaker] = np.vstack([self._enroll[speaker], vecs])
        else:
            self._enroll[speaker] = vecs

    def names(self) -> list[str]:
        """Speaker names in a stable (insertion) order."""
        return list(self._enroll.keys())

    def vectors(self, speaker: str) -> NDArray[np.float32]:
        return self._enroll[speaker]

    def as_list(self, names: list[str] | None = None) -> list[NDArray[np.float32]]:
        """Per-speaker enroll arrays aligned to `names` (default: all, stable order)."""
        return [self._enroll[n] for n in (names if names is not None else self.names())]

    def __contains__(self, speaker: str) -> bool:
        return speaker in self._enroll

    def __len__(self) -> int:
        return len(self._enroll)

    def save(self, directory: str | Path) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        for speaker, vecs in self._enroll.items():
            np.save(d / f"{speaker}.npy", vecs)

    @classmethod
    def load(cls, directory: str | Path) -> Gallery:
        g = cls()
        for path in sorted(Path(directory).glob("*.npy")):
            g._enroll[path.stem] = np.asarray(np.load(path), dtype=np.float32)
        return g
