from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from voxmap.types import Audio, Segment


class Embedder(Protocol):
    def __call__(self, audio: Audio, segments: list[Segment]) -> NDArray[np.float32]: ...
