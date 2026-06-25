from pathlib import Path
from typing import Annotated

import typer
import yaml

from voxmap.io.audio import load_audio
from voxmap.io.rttm import write_rttm
from voxmap.log import get_logger
from voxmap.pipeline.builder import build_pipeline

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
    with config.open() as f:
        cfg = yaml.safe_load(f)

    pipeline = build_pipeline(cfg)
    audio_data = load_audio(audio)
    diarization = pipeline(audio_data, n_speakers=n_speakers)

    resolved_uri = uri or audio.stem
    output.parent.mkdir(parents=True, exist_ok=True)
    write_rttm(diarization, output, uri=resolved_uri)
    log.info("wrote_rttm", n_turns=len(diarization.turns), path=str(output))


if __name__ == "__main__":
    app()
