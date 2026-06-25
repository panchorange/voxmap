from typing import Protocol

from voxmap.types import Audio, Segment


class VAD(Protocol):
    def __call__(self, audio: Audio) -> list[Segment]: ...
