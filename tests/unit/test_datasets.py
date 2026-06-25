"""Unit tests for voxmap.io.datasets path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxmap.io.datasets import (
    DATASETS,
    MeetingPaths,
    load_dataset,
    read_meeting_ids,
)


def _make_ami(repo_root: Path, ids: list[str], split: str = "test") -> None:
    root = repo_root / "data" / "raw" / "ami"
    (root / "setup" / "lists").mkdir(parents=True, exist_ok=True)
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "rttm").mkdir(parents=True, exist_ok=True)
    (root / "setup" / "lists" / f"{split}.meetings.txt").write_text("\n".join(ids) + "\n")
    for mid in ids:
        (root / "audio" / f"{mid}.Mix-Headset.wav").touch()
        (root / "rttm" / f"{mid}.rttm").touch()


def _make_voxconverse(repo_root: Path, ids: list[str], split: str = "test") -> None:
    root = repo_root / "data" / "raw" / "voxconverse"
    (root / "lists").mkdir(parents=True, exist_ok=True)
    (root / "audio" / split).mkdir(parents=True, exist_ok=True)
    (root / "rttm" / split).mkdir(parents=True, exist_ok=True)
    (root / "lists" / f"{split}.txt").write_text("\n".join(ids) + "\n")
    for mid in ids:
        (root / "audio" / split / f"{mid}.wav").touch()
        (root / "rttm" / split / f"{mid}.rttm").touch()


def test_ami_layout(tmp_path: Path) -> None:
    _make_ami(tmp_path, ["IS1009a", "ES2004a"])
    rows = load_dataset("ami", "test", tmp_path)
    assert [r.meeting for r in rows] == ["IS1009a", "ES2004a"]
    assert rows[0].audio_path == tmp_path / "data/raw/ami/audio/IS1009a.Mix-Headset.wav"
    assert rows[0].rttm_path == tmp_path / "data/raw/ami/rttm/IS1009a.rttm"
    assert all(r.audio_path.exists() and r.rttm_path.exists() for r in rows)


def test_voxconverse_layout(tmp_path: Path) -> None:
    _make_voxconverse(tmp_path, ["aepyx", "aggyz"], split="test")
    rows = load_dataset("voxconverse", "test", tmp_path)
    assert [r.meeting for r in rows] == ["aepyx", "aggyz"]
    assert rows[0].audio_path == tmp_path / "data/raw/voxconverse/audio/test/aepyx.wav"
    assert rows[0].rttm_path == tmp_path / "data/raw/voxconverse/rttm/test/aepyx.rttm"


def test_max_files(tmp_path: Path) -> None:
    _make_voxconverse(tmp_path, [f"id{i}" for i in range(10)])
    rows = load_dataset("voxconverse", "test", tmp_path, max_files=3)
    assert len(rows) == 3
    assert [r.meeting for r in rows] == ["id0", "id1", "id2"]


def test_unknown_dataset(tmp_path: Path) -> None:
    with pytest.raises(KeyError, match="unknown dataset"):
        load_dataset("nope", "test", tmp_path)


def test_missing_list(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="meeting list not found"):
        read_meeting_ids("ami", "test", tmp_path)


def test_returns_meeting_paths_namedtuple(tmp_path: Path) -> None:
    _make_ami(tmp_path, ["IS1009a"])
    rows = load_dataset("ami", "test", tmp_path)
    assert isinstance(rows[0], MeetingPaths)


def test_registry_has_known_datasets() -> None:
    assert set(DATASETS) >= {"ami", "voxconverse"}
