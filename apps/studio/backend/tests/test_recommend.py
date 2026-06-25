"""クラスタ粒度の話者レコメンド: 合成重心 + 一時ギャラリで対応表の挙動を検証する。

重いモデルに依存せず、軸ベクトルと cos スコアラで cluster->speaker 対応を確認する。
ギャラリは会議スコープに縛らず gallery 配下の全 npy を横断候補にする。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.recommend import gallery_names, load_full_gallery, propose_cluster_mapping

CONFIG = {"recommend": {"reduction": "centroid", "threshold": 0.5}}


def _axis(dim: int, axis: int) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float32)
    v[axis] = 1.0
    return v


def _write_gallery(root: Path) -> None:
    # 別会議サブフォルダに enroll を置く (会議×人を区別)
    (root / "EN2002a").mkdir(parents=True)
    (root / "cpebh").mkdir(parents=True)
    np.save(root / "EN2002a" / "yamada.npy", np.vstack([_axis(8, 0), _axis(8, 0)]))
    np.save(root / "EN2002a" / "tanaka.npy", np.vstack([_axis(8, 1), _axis(8, 1)]))
    np.save(root / "cpebh" / "distractor.npy", _axis(8, 7))  # 別軸 = 紛らわしい他人


def test_load_full_gallery_keys_by_relative_path(tmp_path: Path) -> None:
    _write_gallery(tmp_path)
    g = load_full_gallery(tmp_path)
    assert set(g.names()) == {"EN2002a/yamada", "EN2002a/tanaka", "cpebh/distractor"}


def test_maps_clusters_across_meetings(tmp_path: Path) -> None:
    _write_gallery(tmp_path)
    # 別会議の音声でも、軸0/軸1 のクラスタは会議をまたいで EN2002a の話者に当たる
    centroids = {"SPEAKER_00": _axis(8, 0), "SPEAKER_01": _axis(8, 1)}
    mapping = {m["cluster"]: m for m in propose_cluster_mapping(centroids, tmp_path, CONFIG)}

    assert mapping["SPEAKER_00"]["speaker"] == "EN2002a/yamada"
    assert mapping["SPEAKER_01"]["speaker"] == "EN2002a/tanaka"
    assert mapping["SPEAKER_00"]["score"] > 0.9


def test_candidates_are_topk_above_tau(tmp_path: Path) -> None:
    _write_gallery(tmp_path)
    centroids = {"SPEAKER_00": _axis(8, 0)}  # 軸0 = yamada のみ高スコア、他は ~0 (τ未満)
    [m] = propose_cluster_mapping(centroids, tmp_path, CONFIG)
    scores = m["scores"]
    # τ未満 (tanaka, distractor ~0) は候補に出ない。yamada だけ。
    assert [c["speaker"] for c in scores] == ["EN2002a/yamada"]
    assert scores[0]["score"] > 0.9


def test_candidates_respect_top_k(tmp_path: Path) -> None:
    # 3 つの既知話者が全員 τ以上に並ぶケースで k=2 に切られる
    (tmp_path / "m").mkdir()
    mixed = (_axis(8, 0) + 0.9 * _axis(8, 1) + 0.8 * _axis(8, 2)).astype(np.float32)
    for i in range(3):
        np.save(tmp_path / "m" / f"s{i}.npy", _axis(8, i))
    cfg = {"recommend": {"reduction": "centroid", "threshold": 0.1, "top_k": 2}}
    [m] = propose_cluster_mapping({"SPEAKER_00": mixed}, tmp_path, cfg)
    assert len(m["scores"]) == 2  # τ以上は3件だが top_k=2 で切る
    vals = [c["score"] for c in m["scores"]]
    assert vals == sorted(vals, reverse=True)


def test_distractor_not_matched_for_novel_cluster(tmp_path: Path) -> None:
    _write_gallery(tmp_path)
    # 軸2 はどの既知話者 (軸0/1/7) にも似ない -> τ未満 -> novel
    centroids = {"SPEAKER_00": _axis(8, 2)}
    [m] = propose_cluster_mapping(centroids, tmp_path, CONFIG)
    assert m["speaker"] is None


def test_no_gallery_all_novel(tmp_path: Path) -> None:
    centroids = {"SPEAKER_00": _axis(8, 0)}
    [m] = propose_cluster_mapping(centroids, tmp_path / "missing", CONFIG)
    assert m["speaker"] is None


def test_gallery_names_lists_all(tmp_path: Path) -> None:
    _write_gallery(tmp_path)
    assert set(gallery_names(tmp_path)) == {
        "EN2002a/yamada",
        "EN2002a/tanaka",
        "cpebh/distractor",
    }
