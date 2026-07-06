from pathlib import Path
from typing import Annotated

import typer

from voxmap.io.audio import load_audio
from voxmap.io.rttm import write_rttm
from voxmap.log import get_logger
from voxmap.pipeline.builder import build_pipeline
from voxmap.types import Diarization, Segment, SpeakerTurn

log = get_logger(__name__)
app = typer.Typer()


@app.command()
def main(
    audio: Annotated[Path, typer.Argument(help="input audio file")],
    config: Annotated[Path, typer.Option(help="pipeline YAML config")],
    output: Annotated[Path, typer.Option("-o", "--output", help="output RTTM path")],
    n_speakers: Annotated[
        int | None, typer.Option(help="fix number of speakers (default: auto)")
    ] = None,
    uri: Annotated[str | None, typer.Option(help="file URI in RTTM (default: audio stem)")] = None,
) -> None:
    """Run speaker diarization on an audio file."""
    pipeline = build_pipeline(config)
    audio_data = load_audio(audio)
    resolved_uri = uri or audio.stem

    # Diarization31Pipeline は pyannote.core.Annotation を返す。RTTM 書き出しは
    # voxmap の write_rttm を再利用するため Diarization へ変換する。
    annotation = pipeline(audio_data, num_speakers=n_speakers, uri=resolved_uri)
    turns = [
        SpeakerTurn(segment=Segment(seg.start, seg.end), speaker=label)
        for seg, _track, label in annotation.itertracks(yield_label=True)
    ]
    diarization = Diarization(turns=turns)

    output.parent.mkdir(parents=True, exist_ok=True)
    write_rttm(diarization, output, uri=resolved_uri)
    log.info("wrote_rttm", n_turns=len(diarization.turns), path=str(output))


if __name__ == "__main__":
    app()
