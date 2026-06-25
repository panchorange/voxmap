from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class Clustering(Protocol):
    def __call__(
        self,
        embeddings: NDArray[np.float32],
        n_speakers: int | None = None,
    ) -> NDArray[np.intp]: ...
