from typing import Protocol

from voxmap.types import Audio, Diarization


class Pipeline(Protocol):
    def __call__(self, audio: Audio, n_speakers: int | None = None) -> Diarization: ...
