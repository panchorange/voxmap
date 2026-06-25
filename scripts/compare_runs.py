"""Compare metrics.json from multiple experiments and emit a markdown table.

Usage:
    uv run python scripts/compare_runs.py <id1> <id2> [<id3> ...] [--out NAME] [--plot]

  <id>: experiments/<theme>/<id>/ の <theme>/<id> (e.g., 2026-05-07_研究テーマ/2026-05-14_campplus)
  --out: output directory name under docs/experiments/comparisons/ (default: auto)
  --plot: also save matplotlib box (DER) / bar (RTF) charts

Output:
    docs/experiments/comparisons/<NAME>/comparison.md
    docs/experiments/comparisons/<NAME>/der_box.png   (if --plot)
    docs/experiments/comparisons/<NAME>/rtf_bar.png   (if --plot)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import polars as pl
import typer

from voxmap.log import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO_ROOT / "experiments"
COMPARISONS_DIR = REPO_ROOT / "docs" / "experiments" / "comparisons"

app = typer.Typer()


def load_metrics(exp_id: str) -> dict[str, Any]:
    path = EXPERIMENTS_DIR / exp_id / "results" / "metrics.json"
    if not path.exists():
        raise typer.BadParameter(
            f"{exp_id}: results/metrics.json が見つかりません (path={path}). "
            "experiment-run で先に走らせてください."
        )
    with path.open() as f:
        data: dict[str, Any] = json.load(f)
    data["exp_id"] = exp_id
    return data


def check_conditions(records: list[dict[str, Any]]) -> list[str]:
    """評価条件 (split / collar / skip_overlap / n_speakers) が揃っているか確認。"""
    keys = ("data_split", "collar", "skip_overlap", "n_speakers", "split")
    warnings: list[str] = []
    base = records[0].get("evaluation", {})
    for r in records[1:]:
        ev = r.get("evaluation", {})
        for k in keys:
            if k in base and k in ev and base[k] != ev[k]:
                warnings.append(f"{k}: {records[0]['exp_id']}={base[k]} vs {r['exp_id']}={ev[k]}")
    return warnings


def build_aggregate_table(records: list[dict[str, Any]]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for r in records:
        m = r["metrics"]
        per_file = r["per_file"]
        n_lost = sum(1 for p in per_file if p["n_speakers_predicted"] < p["n_speakers_reference"])
        loss_rate = n_lost / len(per_file) if per_file else 0.0
        rows.append(
            {
                "exp_id": r["exp_id"],
                "DER (micro)": float(m["der_micro"]),
                "DER (macro)": float(m["der_macro"]),
                "RTF": float(m["rtf"]),
                "n_files": int(m["n_files"]),
                "話者消失率": loss_rate,
            }
        )
    return pl.DataFrame(rows)


def _union_meetings(records: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    meetings: list[str] = []
    for r in records:
        for p in r["per_file"]:
            if p["meeting"] not in seen:
                meetings.append(p["meeting"])
                seen.add(p["meeting"])
    return meetings


def build_per_meeting_der(records: list[dict[str, Any]]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for meeting in _union_meetings(records):
        row: dict[str, Any] = {"meeting": meeting}
        for r in records:
            der = next((p["der"] for p in r["per_file"] if p["meeting"] == meeting), None)
            row[r["exp_id"]] = float(der) if der is not None else None
        rows.append(row)
    return pl.DataFrame(rows)


def build_per_meeting_speaker_diff(records: list[dict[str, Any]]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    reference: dict[str, int] = {}
    for r in records:
        for p in r["per_file"]:
            reference.setdefault(p["meeting"], int(p["n_speakers_reference"]))

    for meeting in _union_meetings(records):
        row: dict[str, Any] = {"meeting": meeting, "reference": reference[meeting]}
        for r in records:
            p_match = next((p for p in r["per_file"] if p["meeting"] == meeting), None)
            row[r["exp_id"]] = (
                int(p_match["n_speakers_predicted"]) - int(p_match["n_speakers_reference"])
                if p_match
                else None
            )
        rows.append(row)
    return pl.DataFrame(rows)


def df_to_markdown(df: pl.DataFrame) -> str:
    headers = df.columns
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in df.iter_rows():
        cells: list[str] = []
        for v in row:
            if v is None:
                cells.append("—")
            elif isinstance(v, float):
                cells.append(f"{v:.4f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_plots(records: list[dict[str, Any]], out_dir: Path) -> tuple[Path, Path]:
    import matplotlib.pyplot as plt

    labels = [r["exp_id"] for r in records]

    fig1, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.boxplot([[p["der"] for p in r["per_file"]] for r in records], tick_labels=labels)
    ax1.set_ylabel("DER (per meeting)")
    ax1.set_title("DER distribution per experiment")
    ax1.tick_params(axis="x", rotation=20)
    fig1.tight_layout()
    der_path = out_dir / "der_box.png"
    fig1.savefig(der_path, dpi=120)
    plt.close(fig1)

    fig2, ax2 = plt.subplots(figsize=(7, 4.5))
    ax2.bar(labels, [r["metrics"]["rtf"] for r in records])
    ax2.set_ylabel("RTF (aggregate)")
    ax2.set_title("RTF per experiment")
    ax2.tick_params(axis="x", rotation=20)
    fig2.tight_layout()
    rtf_path = out_dir / "rtf_bar.png"
    fig2.savefig(rtf_path, dpi=120)
    plt.close(fig2)

    return der_path, rtf_path


def render_markdown(
    records: list[dict[str, Any]],
    warnings: list[str],
    plot_paths: tuple[Path, Path] | None,
) -> str:
    ids = [r["exp_id"] for r in records]
    parts: list[str] = []
    parts.append(f"# 比較: {' vs '.join(ids)}\n")
    parts.append("関連: " + " / ".join(f"[[../{i}]]" for i in ids) + "\n")
    parts.append(
        f"生成: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by `scripts/compare_runs.py`\n"
    )

    eval_df = pl.DataFrame(
        [
            {
                "exp_id": r["exp_id"],
                "split": r.get("evaluation", {}).get("split")
                or r.get("evaluation", {}).get("data_split"),
                "collar": r.get("evaluation", {}).get("collar"),
                "skip_overlap": r.get("evaluation", {}).get("skip_overlap"),
                "device": r.get("device"),
                "git_commit": (r.get("git_commit") or "")[:7],
            }
            for r in records
        ]
    )
    parts.append("## 評価条件\n")
    parts.append(df_to_markdown(eval_df) + "\n")
    if warnings:
        parts.append("> ⚠ 評価条件が揃っていません:")
        for w in warnings:
            parts.append(f"> - {w}")
        parts.append("")

    parts.append("## aggregate\n")
    parts.append(df_to_markdown(build_aggregate_table(records)) + "\n")

    parts.append("## per-meeting (DER)\n")
    parts.append(df_to_markdown(build_per_meeting_der(records)) + "\n")

    parts.append("## per-meeting (話者数推定誤り = predicted - reference)\n")
    parts.append(df_to_markdown(build_per_meeting_speaker_diff(records)) + "\n")

    if plot_paths:
        parts.append("## プロット\n")
        parts.append(f"![DER box]({plot_paths[0].name})\n")
        parts.append(f"![RTF bar]({plot_paths[1].name})\n")

    return "\n".join(parts)


def default_out_name(exp_ids: list[str]) -> str:
    if len(exp_ids) == 2:
        return f"{exp_ids[0]}_vs_{exp_ids[1]}"
    return f"{exp_ids[0]}_etc"


@app.command()
def main(
    exp_ids: Annotated[
        list[str],
        typer.Argument(help="experiments/<theme>/<id>/ の <theme>/<id> を 2 件以上"),
    ],
    out: Annotated[
        str | None,
        typer.Option(help="出力ディレクトリ名 (docs/experiments/comparisons/<NAME>/)"),
    ] = None,
    plot: Annotated[bool, typer.Option(help="box(DER) / bar(RTF) chart を生成")] = False,
) -> None:
    """Compare metrics.json from multiple experiments."""
    if len(exp_ids) < 2:
        raise typer.BadParameter("比較には 2 件以上の実験 ID を指定してください")

    records = [load_metrics(eid) for eid in exp_ids]

    warnings = check_conditions(records)
    for w in warnings:
        log.warning("eval_condition_mismatch", detail=w)

    name = out or default_out_name(exp_ids)
    out_dir = COMPARISONS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_paths = render_plots(records, out_dir) if plot else None
    if plot_paths:
        log.info("plots_saved", der=str(plot_paths[0]), rtf=str(plot_paths[1]))

    md_path = out_dir / "comparison.md"
    md_path.write_text(render_markdown(records, warnings, plot_paths))
    log.info("comparison_written", path=str(md_path), n_experiments=len(records))


if __name__ == "__main__":
    app()
