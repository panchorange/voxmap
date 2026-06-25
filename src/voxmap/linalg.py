"""Leaf-level vector math shared across clustering and scoring.

A neutral home for the cosine primitives that were previously inlined in
`clustering/ahc.py`. Both `clustering/` and `scorer/` depend on this module
(never on each other), keeping the dependency direction acyclic.

`l2_normalize` reproduces the exact upstream pyannote-3.1 normalization used by
AHC (zero vectors -> NaN, divide-ignored), so adopting it in ahc is
behavior-preserving.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def l2_normalize(x: NDArray[np.float32]) -> NDArray[np.float32]:
    """Divide vectors by their L2 norm along the last axis.

    Matches `clustering/ahc.py` upstream behavior: a zero vector yields NaN
    (division warnings suppressed), not a guarded fallback.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        # Preserve input dtype (do not force float32): ahc feeds the result to
        # scipy linkage and must stay numerically identical to the prior inline code.
        return x / np.linalg.norm(x, axis=-1, keepdims=True)  # type: ignore[no-any-return]


def cosine_similarity(a: NDArray[np.float32], b: NDArray[np.float32]) -> NDArray[np.float32]:
    """Cosine similarity matrix between rows of `a` (Q, D) and `b` (M, D) -> (Q, M).

    Higher is more similar (range [-1, 1]). Inputs are L2-normalized internally.
    """
    an = l2_normalize(np.atleast_2d(a))
    bn = l2_normalize(np.atleast_2d(b))
    return np.asarray(an @ bn.T, dtype=np.float32)
