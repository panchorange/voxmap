from pyannote.audio.pipelines import VoiceActivityDetection

from voxmap.types import Audio, Segment


class PyannoteVAD:
    def __init__(
        self,
        segmentation_model: str = "pyannote/segmentation-3.0",
        auth_token: str | None = None,
        min_duration_on: float = 0.0,
        min_duration_off: float = 0.0,
    ) -> None:
        self._pipeline = VoiceActivityDetection(
            segmentation=segmentation_model,
            token=auth_token,
        )
        self._pipeline.instantiate(
            {"min_duration_on": min_duration_on, "min_duration_off": min_duration_off}
        )

    def __call__(self, audio: Audio) -> list[Segment]:
        annotation = self._pipeline({"waveform": audio.waveform, "sample_rate": audio.sample_rate})
        return [Segment(start=float(s.start), end=float(s.end)) for s in annotation.get_timeline()]
