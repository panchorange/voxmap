"""word↔speaker fusion の割当ロジックを検証する (純関数なので NeMo 不要)。"""

from voxmap.asr_diarization import assign_speakers
from voxmap.asr_diarization.pipeline import ASRDiarizationPipeline
from voxmap.types import (
    Audio,
    Diarization,
    Segment,
    SpeakerTurn,
    Transcript,
    Word,
)


def _diar() -> Diarization:
    return Diarization(
        turns=[
            SpeakerTurn(Segment(0.0, 5.0), "speaker_00"),
            SpeakerTurn(Segment(5.0, 10.0), "speaker_01"),
        ]
    )


def test_word_assigned_to_max_overlap_speaker() -> None:
    transcript = Transcript(words=[Word("hello", 0.5, 1.5), Word("world", 6.0, 7.0)])
    out = assign_speakers(transcript, _diar())
    assert [w.speaker for w in out.words] == ["speaker_00", "speaker_01"]


def test_word_straddling_boundary_goes_to_larger_overlap() -> None:
    # 4.0–4.8 が spk00 (0.8), 5.0–5.2 が spk01 (0.2) → spk00
    transcript = Transcript(words=[Word("edge", 4.0, 5.2)])
    out = assign_speakers(transcript, _diar())
    assert out.words[0].speaker == "speaker_00"


def test_word_with_no_overlap_falls_back_to_nearest_turn() -> None:
    transcript = Transcript(words=[Word("late", 12.0, 12.5)])  # 全 turn の外
    out = assign_speakers(transcript, _diar())
    assert out.words[0].speaker == "speaker_01"  # 10.0 に近い方


def test_empty_diarization_uses_fallback() -> None:
    transcript = Transcript(words=[Word("orphan", 1.0, 2.0)])
    out = assign_speakers(transcript, Diarization(turns=[]), fallback_speaker="UNK")
    assert out.words[0].speaker == "UNK"


def test_by_speaker_concatenates_text_in_order() -> None:
    transcript = Transcript(words=[Word("a", 0.1, 0.2), Word("b", 6.0, 6.1), Word("c", 0.3, 0.4)])
    out = assign_speakers(transcript, _diar())
    assert out.by_speaker() == {"speaker_00": "a c", "speaker_01": "b"}


def test_pipeline_serial_fuses_and_times_stages() -> None:
    audio = Audio(waveform=None, sample_rate=16000)  # type: ignore[arg-type]
    diar = _diar()
    transcript = Transcript(words=[Word("hi", 0.5, 1.0)])
    pipe = ASRDiarizationPipeline(
        diarize=lambda a, **kw: diar, asr=lambda a: transcript, mode="serial"
    )
    res = pipe(audio)
    assert res.mode == "serial"
    assert res.attributed.words[0].speaker == "speaker_00"
    assert res.diarization is diar
    assert res.wall_seconds >= 0.0
