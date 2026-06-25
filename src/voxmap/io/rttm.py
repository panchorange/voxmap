from pathlib import Path

from voxmap.types import Diarization, Segment, SpeakerTurn


def write_rttm(diar: Diarization, path: str | Path, uri: str) -> None:
    with Path(path).open("w") as f:
        for turn in diar.turns:
            seg = turn.segment
            f.write(
                f"SPEAKER {uri} 1 {seg.start:.3f} {seg.duration:.3f} "
                f"<NA> <NA> {turn.speaker} <NA> <NA>\n"
            )


def read_rttm(path: str | Path) -> Diarization:
    turns: list[SpeakerTurn] = []
    with Path(path).open() as f:
        for line in f:
            parts = line.strip().split()
            if not parts or parts[0] != "SPEAKER":
                continue
            start = float(parts[3])
            duration = float(parts[4])
            speaker = parts[7]
            turns.append(SpeakerTurn(segment=Segment(start, start + duration), speaker=speaker))
    return Diarization(turns=turns)
