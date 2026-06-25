"""Visualize a diarization pipeline's internals for a few meetings.

Builds the *exact* pipeline an experiment `config.yaml` describes
(`voxmap.eval.build.build_pipeline_from_config`), runs it on the chosen meetings
while capturing segmentation / speaker-count / embeddings via the pipeline hook,
and emits per-meeting figures + a `report.md` of cluster metrics — all through
`voxmap.eval.visualize`, so the clusters shown are the production AHC's.

This is the reusable launcher invoked by the `analysis-run` skill. Per-analysis
`analysis/<id>/analyze.py` can call this CLI, or import the same lib helpers
directly for question-specific plots.

Usage:
    uv run python scripts/analyze_pipeline.py \
        --config experiments/2026-05-19_stride3/config.yaml \
        --meetings IS1009a,EN2002c --out analysis/<id>/results/stride3
"""

from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from voxmap.eval.build import build_pipeline_from_config  # noqa: E402
from voxmap.eval.visualize import diagnose_meeting, load_audio, run_with_hooks  # noqa: E402
from voxmap.io.rttm import read_rttm  # noqa: E402

DATASET_PATHS: dict[str, dict[str, str]] = {
    "ami": {
        "audio_dir": "data/raw/ami/audio",
        "rttm_dir": "data/raw/ami/rttm",
        "audio_suffix": ".Mix-Headset.wav",
    },
    "voxconverse": {
        "audio_dir": "data/raw/voxconverse/audio",
        "rttm_dir": "data/raw/voxconverse/rttm",
        "audio_suffix": ".wav",
    },
}


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, str]:
    preset = DATASET_PATHS[args.dataset]
    audio_dir = Path(args.audio_dir or REPO_ROOT / preset["audio_dir"])
    rttm_dir = Path(args.rttm_dir or REPO_ROOT / preset["rttm_dir"])
    suffix = args.audio_suffix if args.audio_suffix is not None else preset["audio_suffix"]
    return audio_dir, rttm_dir, suffix


def _write_report(out_dir: Path, config_path: Path, rows: list[dict[str, Any]]) -> Path:
    lines = [
        f"# Pipeline analysis — {config_path.name}",
        "",
        f"config: `{config_path}`",
        "",
        "| meeting | pred | ref | count_err | n_segments | cluster_purity |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['meeting']} | {r['n_speakers_pred']} | {r['n_speakers_ref']} "
            f"| {r['count_error']:+d} | {r['n_segments']} | {r['cluster_purity']} |"
        )
    if rows:
        mean_purity = sum(r["cluster_purity"] for r in rows) / len(rows)
        mean_abs_err = sum(abs(r["count_error"]) for r in rows) / len(rows)
        lines += [
            "",
            f"mean cluster_purity: {mean_purity:.4f}  /  mean |count_error|: {mean_abs_err:.2f}",
        ]
    report = out_dir / "report.md"
    report.write_text("\n".join(lines) + "\n")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True, type=Path, help="experiment config.yaml")
    p.add_argument("--meetings", required=True, help="comma-separated meeting ids")
    p.add_argument("--dataset", default="ami", choices=sorted(DATASET_PATHS))
    p.add_argument("--out", required=True, type=Path, help="output dir for figures + report")
    p.add_argument("--audio-dir", default=None, help="override dataset audio dir")
    p.add_argument("--rttm-dir", default=None, help="override dataset rttm dir")
    p.add_argument("--audio-suffix", default=None, help="override audio filename suffix")
    p.add_argument("--no-cache", action="store_true", help="ignore cached intermediates")
    args = p.parse_args()

    config_path = args.config.resolve()
    config: dict[str, Any] = yaml.safe_load(config_path.read_text())
    audio_dir, rttm_dir, suffix = _resolve_paths(args)

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache"
    cache_dir.mkdir(exist_ok=True)

    meetings = [m.strip() for m in args.meetings.split(",") if m.strip()]
    print(f"building pipeline from {config_path.name} ...")
    pipeline, device = build_pipeline_from_config(config)
    print(f"  device={device}  meetings={meetings}")

    rows: list[dict[str, Any]] = []
    for meeting in meetings:
        audio_path = audio_dir / f"{meeting}{suffix}"
        rttm_path = rttm_dir / f"{meeting}.rttm"
        if not audio_path.exists() or not rttm_path.exists():
            print(f"  [skip] {meeting}: audio or rttm missing")
            continue

        cache_path = cache_dir / f"{meeting}.pkl"
        captured: dict[str, Any] | None = None
        if cache_path.exists() and not args.no_cache:
            print(f"  [cached] {meeting}")
            with cache_path.open("rb") as f:
                captured = pickle.load(f)
        else:
            print(f"  [run] {meeting}")
            captured = run_with_hooks(pipeline, load_audio(audio_path), meeting)
            with cache_path.open("wb") as f:
                pickle.dump(captured, f)

        reference = read_rttm(rttm_path)
        metrics = diagnose_meeting(
            pipeline, load_audio(audio_path), reference, meeting, out_dir, captured=captured
        )
        metrics["meeting"] = meeting
        rows.append(metrics)
        print(
            f"    -> pred {metrics['n_speakers_pred']} / ref {metrics['n_speakers_ref']} "
            f"(err {metrics['count_error']:+d})  purity={metrics['cluster_purity']}"
        )

    report = _write_report(out_dir, config_path, rows)
    print(f"\nfigures + report: {report}")


if __name__ == "__main__":
    main()
