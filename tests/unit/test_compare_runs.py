"""Smoke tests for scripts/compare_runs.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from compare_runs import (  # noqa: E402
    app,
    build_aggregate_table,
    check_conditions,
    default_out_name,
    df_to_markdown,
)

RUNNER = CliRunner()

_METRICS_TEMPLATE: dict[str, object] = {
    "metrics": {
        "der_micro": 0.12,
        "der_macro": 0.15,
        "rtf": 0.08,
        "n_files": 2,
    },
    "per_file": [
        {
            "meeting": "mtg_a",
            "der": 0.10,
            "n_speakers_reference": 3,
            "n_speakers_predicted": 3,
        },
        {
            "meeting": "mtg_b",
            "der": 0.14,
            "n_speakers_reference": 2,
            "n_speakers_predicted": 1,
        },
    ],
    "evaluation": {
        "data_split": "test",
        "collar": 0.25,
        "skip_overlap": False,
    },
    "device": "cpu",
    "git_commit": "abc1234",
}


def _write_metrics(base: Path, exp_id: str, overrides: dict[str, object] | None = None) -> Path:
    data = json.loads(json.dumps(_METRICS_TEMPLATE))
    if overrides:
        data.update(overrides)
    exp_dir = base / "experiments" / exp_id / "results"
    exp_dir.mkdir(parents=True)
    (exp_dir / "metrics.json").write_text(json.dumps(data))
    return base


def test_default_out_name_two() -> None:
    assert default_out_name(["a", "b"]) == "a_vs_b"


def test_default_out_name_three() -> None:
    assert default_out_name(["a", "b", "c"]) == "a_etc"


def test_df_to_markdown_basic() -> None:
    import polars as pl

    df = pl.DataFrame({"x": [1], "y": [0.5]})
    md = df_to_markdown(df)
    assert "| x | y |" in md
    assert "0.5000" in md


def test_check_conditions_no_mismatch() -> None:
    records = [
        {"exp_id": "a", "evaluation": {"collar": 0.25, "skip_overlap": False}},
        {"exp_id": "b", "evaluation": {"collar": 0.25, "skip_overlap": False}},
    ]
    assert check_conditions(records) == []


def test_check_conditions_mismatch() -> None:
    records = [
        {"exp_id": "a", "evaluation": {"collar": 0.25}},
        {"exp_id": "b", "evaluation": {"collar": 0.50}},
    ]
    warnings = check_conditions(records)
    assert len(warnings) == 1
    assert "collar" in warnings[0]


def test_build_aggregate_table_speaker_loss() -> None:
    records = [
        {
            "exp_id": "exp_a",
            "metrics": {"der_micro": 0.1, "der_macro": 0.1, "rtf": 0.05, "n_files": 2},
            "per_file": [
                {"meeting": "m1", "der": 0.1, "n_speakers_reference": 2, "n_speakers_predicted": 1},
                {"meeting": "m2", "der": 0.1, "n_speakers_reference": 3, "n_speakers_predicted": 3},
            ],
        }
    ]
    df = build_aggregate_table(records)
    row = df.row(0, named=True)
    assert row["話者消失率"] == pytest.approx(0.5)


def test_cli_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: script runs without error and writes comparison.md."""
    _write_metrics(tmp_path, "exp_a")
    _write_metrics(tmp_path, "exp_b")
    out_dir = tmp_path / "docs" / "experiments" / "comparisons"
    out_dir.mkdir(parents=True)

    import compare_runs as cr

    monkeypatch.setattr(cr, "EXPERIMENTS_DIR", tmp_path / "experiments")
    monkeypatch.setattr(cr, "COMPARISONS_DIR", out_dir)

    result = RUNNER.invoke(app, ["exp_a", "exp_b"])
    assert result.exit_code == 0, result.output
    assert (out_dir / "exp_a_vs_exp_b" / "comparison.md").exists()
