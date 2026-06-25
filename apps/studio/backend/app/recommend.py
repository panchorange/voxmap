"""クラスタ粒度の話者レコメンド (設計 §4.4 / §6.1 の一括対応)。

分離直後、各 auto クラスタ (speaker_00 …) の重心を、ギャラリ配下の**全既知話者**へ
横断照合し、`speaker_00 → 田中` の対応表 (top-1 + τ棄却) を出す。重心は分離が算出済みの
ものを再利用するため追加の埋め込み計算はゼロ (設計 §7、RTF 影響なし)。

ギャラリは会議スコープに縛らない: `gallery/<会議>/<話者>.npy` を再帰的に集め、
各 npy を 1 つの既知話者 (会議×人) として候補にする。別会議の音声でも、その音声の
話者がギャラリ内にいれば対応づく (いなければ全クラスタ新規)。

segment 粒度の怪しさ判定 (②③④) はここには含めない (別段の拡張)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from numpy.typing import NDArray
from voxmap.recommend.enrollment import Gallery
from voxmap.recommend.recommender import Recommender
from voxmap.scorer.cos import CosScorer


class CandidateDict(TypedDict):
    speaker: str
    score: float


class ClusterMappingDict(TypedDict):
    cluster: str
    speaker: str | None  # None = どの既知話者も τ 未満 → 新規話者 (Hungarian の既定割当)
    score: float
    # 全既知話者へのスコア (降順)。UI でドロップダウン選択を変えたとき表示を更新する用。
    scores: list[CandidateDict]


def load_full_gallery(gallery_root: Path) -> Gallery:
    """gallery 配下の全 npy を 1 話者ずつ横断的にロードする。

    新構造: `gallery/<meeting>/vector/<speaker>.npy` → 話者名 `<meeting>/<speaker>`
    旧構造: `gallery/<meeting>/<speaker>.npy` → 話者名 `<meeting>/<speaker>` (後方互換)
    """
    gallery = Gallery()
    if not gallery_root.is_dir():
        return gallery
    for path in sorted(gallery_root.rglob("*.npy")):
        rel = path.relative_to(gallery_root)
        # vector/ ディレクトリを名前から除く: <meeting>/vector/<speaker> → <meeting>/<speaker>
        parts = rel.with_suffix("").parts
        filtered = [p for p in parts if p != "vector"]
        name = str(Path(*filtered))
        gallery.add(name, np.asarray(np.load(path), dtype=np.float32))
    return gallery


def _build_scorer(config: dict[str, Any]) -> CosScorer:
    r = config.get("recommend", {})
    return CosScorer(reduction=str(r.get("reduction", "centroid")))


def _threshold(config: dict[str, Any]) -> float:
    return float(config.get("recommend", {}).get("threshold", 0.5))


def _top_k(config: dict[str, Any]) -> int:
    return int(config.get("recommend", {}).get("top_k", 3))


def gallery_names(gallery_root: Path) -> list[str]:
    """対応表ドロップダウン用に、全既知話者名を列挙する。"""
    return list(load_full_gallery(gallery_root).names())


def _topk_candidates(
    centroids: dict[str, NDArray[np.float32]],
    gallery: Gallery,
    scorer: CosScorer,
    threshold: float,
    top_k: int,
) -> dict[str, list[CandidateDict]]:
    """各クラスタ重心 × 全既知話者の cos を計算し、クラスタごとに **τ以上の上位 k 件** を返す。

    τ未満 (棄却域) は候補に出さない。該当が無ければ空 (UI では「新規話者」のみ)。
    """
    names = gallery.names()
    clusters = list(centroids)
    if not names or not clusters:
        return {c: [] for c in clusters}
    queries = np.vstack(
        [np.atleast_2d(centroids[c]).mean(axis=0) for c in clusters]
    ).astype(np.float32)
    mat = scorer.score_matrix(queries, gallery.as_list(names))  # (C, S)
    out: dict[str, list[CandidateDict]] = {}
    for i, c in enumerate(clusters):
        cands: list[CandidateDict] = [
            {"speaker": names[j], "score": float(mat[i, j])}
            for j in range(len(names))
            if float(mat[i, j]) >= threshold
        ]
        cands.sort(key=lambda p: p["score"], reverse=True)
        out[c] = cands[:top_k]
    return out


def propose_cluster_mapping(
    centroids: dict[str, NDArray[np.float32]],
    gallery_root: Path,
    config: dict[str, Any],
) -> list[ClusterMappingDict]:
    """auto クラスタ重心 → 全既知話者の最適 1対1 対応 (Hungarian, τ未満は新規)。

    既定の割当 (speaker/score) に加え、全既知話者へのスコア (scores) も付ける。
    ギャラリが空なら全クラスタを「新規 (speaker=None)」で返す。
    """
    gallery = load_full_gallery(gallery_root)
    scorer = _build_scorer(config)
    threshold = _threshold(config)
    recommender = Recommender(scorer=scorer, gallery=gallery, threshold=threshold)
    proposal = recommender.propose_mapping(centroids)
    candidates = _topk_candidates(centroids, gallery, scorer, threshold, _top_k(config))
    return [
        {
            "cluster": m.cluster,
            "speaker": m.speaker,
            "score": m.score,
            "scores": candidates.get(m.cluster, []),
        }
        for m in proposal.mappings
    ]
