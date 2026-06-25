from typing import Protocol

from voxmap.types import Audio, Transcript


class ASR(Protocol):
    def __call__(self, audio: Audio) -> Transcript: ...
