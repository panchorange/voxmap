"""データセットのレイアウト宣言とパス解決。

各データセットは `data/raw/<name>/` 以下に独自のファイル命名で配置される。
`DatasetSpec` がその命名をテンプレートとして宣言し、`load_dataset` が
split ごとの meeting list を読んで (id, audio_path, rttm_path) を解決する。

新しいデータセットを足すときは `DATASETS` にエントリを追加するだけでよい。
推論コード (experiments/<id>/run.py) は dataset 名と split を渡すだけで、
ファイル命名の差異を意識しなくて済む。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple


class MeetingPaths(NamedTuple):
    meeting: str
    audio_path: Path
    rttm_path: Path


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """`data/raw/<name>/` 起点の相対パステンプレート。

    テンプレートは `{split}` と `{id}` を `str.format` で埋める。
    split を持たないデータセットでも `{split}` を含めなければよい。
    """

    name: str
    audio_template: str
    rttm_template: str
    list_template: str


DATASETS: dict[str, DatasetSpec] = {
    "ami": DatasetSpec(
        name="ami",
        audio_template="audio/{id}.Mix-Headset.wav",
        rttm_template="rttm/{id}.rttm",
        list_template="setup/lists/{split}.meetings.txt",
    ),
    "voxconverse": DatasetSpec(
        name="voxconverse",
        audio_template="audio/{split}/{id}.wav",
        rttm_template="rttm/{split}/{id}.rttm",
        list_template="lists/{split}.txt",
    ),
    # MSDWild: split は few.train | few.val | many.val (公式 'test' は無く val が held-out 評価用)。
    "msdwild": DatasetSpec(
        name="msdwild",
        audio_template="audio/{split}/{id}.wav",
        rttm_template="rttm/{split}/{id}.rttm",
        list_template="lists/{split}.txt",
    ),
}


def dataset_root(name: str, repo_root: Path) -> Path:
    return repo_root / "data" / "raw" / name


def read_meeting_ids(name: str, split: str, repo_root: Path) -> list[str]:
    """split の meeting list ファイルから id を 1 行 1 件で読む。"""
    spec = _get_spec(name)
    list_path = dataset_root(name, repo_root) / spec.list_template.format(split=split)
    if not list_path.exists():
        raise FileNotFoundError(f"meeting list not found: {list_path}")
    return [line.strip() for line in list_path.read_text().splitlines() if line.strip()]


def load_dataset(
    name: str,
    split: str,
    repo_root: Path,
    max_files: int | None = None,
) -> list[MeetingPaths]:
    """dataset/split の (meeting, audio_path, rttm_path) を解決して返す。

    パスの存在チェックはしない (呼び出し側で欠損ファイルを扱う)。
    """
    spec = _get_spec(name)
    root = dataset_root(name, repo_root)
    ids = read_meeting_ids(name, split, repo_root)
    if max_files is not None:
        ids = ids[:max_files]
    return [
        MeetingPaths(
            meeting=mid,
            audio_path=root / spec.audio_template.format(split=split, id=mid),
            rttm_path=root / spec.rttm_template.format(split=split, id=mid),
        )
        for mid in ids
    ]


def _get_spec(name: str) -> DatasetSpec:
    try:
        return DATASETS[name]
    except KeyError:
        raise KeyError(f"unknown dataset {name!r}; known: {sorted(DATASETS)}") from None
