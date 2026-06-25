"""Reference baseline: run pyannote.audio's pretrained pipeline as a black box.

Loads `pyannote.audio.Pipeline.from_pretrained` directly (NOT through voxmap's
Protocol/registry) and benchmarks it on AMI. Used by Phase 0 baseline experiments
that establish "pyannote 4.x out-of-the-box" DER and RTF for later optimization
work to compare against.

Each experiment using this script provides its own `config.yaml` and `results/`
under `experiments/<id>/`.

Usage:
    uv run python scripts/run_pyannote_pretrained.py \\
        --experiment-dir experiments/2026-05-07_pyannote4_pretrained_baseline
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import torch
import typer
import yaml
from pyannote.audio import Pipeline
from pyannote.core import Annotation

from voxmap.eval.der import compute_der
from voxmap.io.rttm import read_rttm
from voxmap.log import get_logger
from voxmap.types import Diarization, Segment, SpeakerTurn

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
AMI_AUDIO_DIR = REPO_ROOT / "data/raw/ami/audio"
AMI_RTTM_DIR = REPO_ROOT / "data/raw/ami/rttm"
AMI_SPLIT_DIR = REPO_ROOT / "data/raw/ami/setup/lists"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()


def env_info() -> dict[str, str]:
    info: dict[str, str] = {"python": sys.version.split()[0]}
    for pkg in ("torch", "torchaudio", "pyannote.audio", "pyannote.metrics"):
        try:
            info[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            pass
    return info


def load_meeting_list(split: str, max_files: int | None) -> list[str]:
    path = AMI_SPLIT_DIR / f"{split}.meetings.txt"
    meetings = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return meetings[:max_files] if max_files else meetings


def annotation_to_diarization(annotation: Annotation) -> Diarization:
    """pyannote Annotation → voxmap Diarization (so voxmap eval can be reused)."""
    turns: list[SpeakerTurn] = []
    for segment, _track, label in annotation.itertracks(yield_label=True):
        turns.append(
            SpeakerTurn(
                segment=Segment(float(segment.start), float(segment.end)),
                speaker=str(label),
            )
        )
    return Diarization(turns=turns)


def write_pyannote_rttm(annotation: Annotation, path: Path, uri: str) -> None:
    annotation.uri = uri
    with path.open("w") as f:
        annotation.write_rttm(f)


def resolve_device(name: str) -> torch.device:
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


app = typer.Typer()


@app.command()
def main(
    experiment_dir: Annotated[
        Path, typer.Option(help="experiment directory containing config.yaml")
    ],
    max_files: Annotated[int | None, typer.Option(help="limit for smoke test")] = None,
    split: Annotated[str | None, typer.Option(help="override split from config")] = None,
) -> None:
    """Run pyannote pretrained pipeline on AMI and dump metrics.json + RTTMs."""
    experiment_dir = experiment_dir.resolve()
    config: dict[str, Any] = yaml.safe_load((experiment_dir / "config.yaml").read_text())

    pipeline_cfg = config["pipeline"]
    model_id: str = pipeline_cfg["model"]
    device = resolve_device(pipeline_cfg.get("device", "auto"))
    token: str | None = os.environ.get("HF_TOKEN")

    eval_cfg = config.get("evaluation", {})
    resolved_split: str = split or eval_cfg.get("data_split", "test")
    n_speakers: int | None = eval_cfg.get("n_speakers")
    collar: float = float(eval_cfg.get("collar", 0.0))
    skip_overlap: bool = bool(eval_cfg.get("skip_overlap", False))

    log.info("loading_pipeline", model=model_id, device=str(device))
    pipeline = Pipeline.from_pretrained(model_id, token=token)
    if pipeline is None:
        raise RuntimeError(
            f"Pipeline.from_pretrained({model_id!r}) returned None — "
            "check HF_TOKEN env var and model license access on Hugging Face Hub"
        )
    pipeline.to(device)

    meetings = load_meeting_list(resolved_split, max_files)
    log.info("running", model=model_id, n_meetings=len(meetings), split=resolved_split)

    results_dir = experiment_dir / "results"
    rttm_dir = results_dir / "rttm"
    rttm_dir.mkdir(parents=True, exist_ok=True)

    per_file: list[dict[str, Any]] = []
    data_manifest: list[dict[str, Any]] = []
    total_audio_seconds = 0.0
    total_inference_seconds = 0.0

    for meeting in meetings:
        audio_path = AMI_AUDIO_DIR / f"{meeting}.Mix-Headset.wav"
        ref_path = AMI_RTTM_DIR / f"{meeting}.rttm"
        if not audio_path.exists() or not ref_path.exists():
            log.warning("skip_meeting", meeting=meeting, reason="audio_or_ref_missing")
            continue

        log.info("processing", meeting=meeting)
        with wave.open(str(audio_path), "rb") as wav:
            audio_seconds = wav.getnframes() / wav.getframerate()

        kwargs: dict[str, Any] = {}
        if n_speakers is not None:
            kwargs["num_speakers"] = n_speakers

        start = time.perf_counter()
        result = pipeline(str(audio_path), **kwargs)
        elapsed = time.perf_counter() - start

        # pyannote-audio 4.x returns a DiarizeOutput dataclass; the speaker_diarization
        # field is the pyannote.core.Annotation (overlapping speech turns kept).
        annotation = result.speaker_diarization

        hyp_path = rttm_dir / f"{meeting}.rttm"
        write_pyannote_rttm(annotation, hyp_path, uri=meeting)

        diar = annotation_to_diarization(annotation)
        reference = read_rttm(ref_path)
        components = compute_der(reference, diar, collar=collar, skip_overlap=skip_overlap)

        per_file.append(
            {
                "meeting": meeting,
                "audio_seconds": audio_seconds,
                "inference_seconds": elapsed,
                "rtf": elapsed / audio_seconds,
                "n_speakers_predicted": len(diar.speakers),
                "n_speakers_reference": len(reference.speakers),
                **components,
            }
        )
        data_manifest.append(
            {
                "meeting": meeting,
                "audio_path": str(audio_path.relative_to(REPO_ROOT)),
                "audio_sha256": sha256_of(audio_path),
                "rttm_path": str(ref_path.relative_to(REPO_ROOT)),
                "rttm_sha256": sha256_of(ref_path),
            }
        )
        total_audio_seconds += audio_seconds
        total_inference_seconds += elapsed
        log.info(
            "meeting_done",
            meeting=meeting,
            der=round(components["der"], 4),
            rtf=round(elapsed / audio_seconds, 3),
        )

    sum_total = sum(float(r["total"]) for r in per_file)
    weighted_der = (
        sum(
            float(r["false_alarm"]) + float(r["missed_detection"]) + float(r["confusion"])
            for r in per_file
        )
        / sum_total
        if sum_total > 0
        else 0.0
    )
    macro_der = sum(float(r["der"]) for r in per_file) / len(per_file) if per_file else 0.0

    metrics = {
        "der_micro": weighted_der,
        "der_macro": macro_der,
        "rtf": total_inference_seconds / total_audio_seconds if total_audio_seconds > 0 else 0.0,
        "total_audio_seconds": total_audio_seconds,
        "total_inference_seconds": total_inference_seconds,
        "n_files": len(per_file),
    }

    summary = {
        "config_snapshot": config,
        "data_manifest": data_manifest,
        "git_commit": git_commit(),
        "device": str(device),
        "evaluation": {
            "split": resolved_split,
            "n_speakers": n_speakers,
            "collar": collar,
            "skip_overlap": skip_overlap,
        },
        "metrics": metrics,
        "per_file": per_file,
        "env": env_info(),
        "completed_at": datetime.now(UTC).isoformat(),
    }
    (results_dir / "metrics.json").write_text(json.dumps(summary, indent=2))

    log.info(
        "aggregate",
        n_files=len(per_file),
        der_micro=round(weighted_der, 4),
        der_macro=round(macro_der, 4),
        rtf=round(metrics["rtf"], 3),
        metrics_path=str(results_dir / "metrics.json"),
    )


if __name__ == "__main__":
    app()
