from dataclasses import dataclass

import torch


@dataclass(frozen=True, slots=True)
class Segment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True, slots=True, eq=False)
class Audio:
    waveform: torch.Tensor
    sample_rate: int


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class Transcript:
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    segment: Segment
    speaker: str


@dataclass(frozen=True, slots=True)
class Diarization:
    turns: list[SpeakerTurn]

    @property
    def speakers(self) -> set[str]:
        return {t.speaker for t in self.turns}


@dataclass(frozen=True, slots=True)
class AttributedWord:
    """A transcribed word with a speaker label attached (ASR × diarization)."""

    text: str
    start: float
    end: float
    speaker: str


@dataclass(frozen=True, slots=True)
class AttributedTranscript:
    """Speaker-attributed transcript: the output of fusing ASR + diarization."""

    words: list[AttributedWord]

    @property
    def speakers(self) -> set[str]:
        return {w.speaker for w in self.words}

    def by_speaker(self) -> dict[str, str]:
        """Concatenated text per speaker (the form cpWER consumes)."""
        out: dict[str, list[str]] = {}
        for w in self.words:
            out.setdefault(w.speaker, []).append(w.text)
        return {spk: " ".join(toks) for spk, toks in out.items()}
