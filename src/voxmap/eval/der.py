from pyannote.core import Annotation
from pyannote.core import Segment as PyannoteSegment
from pyannote.metrics.diarization import DiarizationErrorRate, JaccardErrorRate

from voxmap.types import Diarization


def to_annotation(diar: Diarization, uri: str | None = None) -> Annotation:
    annotation = Annotation(uri=uri)
    for i, turn in enumerate(diar.turns):
        annotation[PyannoteSegment(turn.segment.start, turn.segment.end), i] = turn.speaker
    return annotation


def compute_der(
    reference: Diarization,
    hypothesis: Diarization,
    collar: float = 0.0,
    skip_overlap: bool = False,
) -> dict[str, float]:
    metric = DiarizationErrorRate(collar=collar, skip_overlap=skip_overlap)
    components = metric(
        to_annotation(reference, uri="ref"),
        to_annotation(hypothesis, uri="hyp"),
        detailed=True,
    )
    total = float(components.get("total", 0.0))
    der = (
        float(components["false alarm"] + components["missed detection"] + components["confusion"])
        / total
        if total > 0
        else 0.0
    )
    return {
        "der": der,
        "false_alarm": float(components["false alarm"]),
        "missed_detection": float(components["missed detection"]),
        "confusion": float(components["confusion"]),
        "total": total,
    }


def compute_jer(reference: Diarization, hypothesis: Diarization) -> float:
    metric = JaccardErrorRate()  # type: ignore[no-untyped-call]
    return float(metric(to_annotation(reference, uri="ref"), to_annotation(hypothesis, uri="hyp")))
