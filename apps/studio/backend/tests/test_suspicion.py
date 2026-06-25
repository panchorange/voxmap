"""compute_suspicion の単体テスト (voxmap モデルロード不要、合成データ)。

2 クラスタ・2次元埋め込みで、混入 (intruder) と正常 (ok) を作り分けて検証する。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np

from app.suspicion import (
    RecommendationDict,
    SuspicionDict,
    compute_recommendations,
    compute_suspicion,
)

# chunk ごとに 1 local_speaker。chunk c は時刻 [c, c+1) を覆う。
# cluster 0 ≈ [1,0] 方向、cluster 1 ≈ [0,1] 方向。chunk3 は cluster0 割当だが
# 埋め込みは [0,1] = cluster1 寄り → 混入 (intruder)。
_EMB = np.array(
    [[[1.0, 0.0]], [[0.9, 0.1]], [[0.0, 1.0]], [[0.0, 1.0]]], dtype=np.float32
)  # (4 chunks, 1 speaker, 2 dim)
_HARD = np.array([[0], [0], [1], [0]], dtype=np.int64)  # (4, 1)
_SEG_DATA = np.ones((4, 10, 1), dtype=np.float32)  # (chunks, frames, speakers) 全活性
_SW = SimpleNamespace(start=0.0, step=1.0, duration=1.0)
_LABELS = {0: "SPEAKER_00", 1: "SPEAKER_01"}


def _run(segments: list[dict[str, Any]], delta: float = 0.05) -> list[SuspicionDict]:
    return compute_suspicion(segments, _EMB, _HARD, _SEG_DATA, _SW, _LABELS, delta)


def test_intruder_detected() -> None:
    # chunk3 (= 時刻 3-4s) は cluster0 割当だが [0,1] なので別クラスタの方が近い。
    out = _run([{"start": 3.0, "end": 4.0, "speaker": "SPEAKER_00"}])
    assert out[0]["label"] == "intruder"
    assert out[0]["margin"] is not None and out[0]["margin"] < 0
    assert out[0]["nearest"] == "SPEAKER_01"


def test_clean_segment_ok() -> None:
    # chunk0 (= 0-1s) は cluster0 の純粋な代表 [1,0] → ok。
    out = _run([{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}])
    assert out[0]["label"] == "ok"
    assert out[0]["margin"] is not None and out[0]["margin"] > 0


def test_no_member_returns_ok_none() -> None:
    # 該当する埋め込みが時間窓に無い (10-11s) → 判定不能。
    out = _run([{"start": 10.0, "end": 11.0, "speaker": "SPEAKER_00"}])
    assert out[0]["label"] == "ok"
    assert out[0]["margin"] is None


def _rec(segments: list[dict[str, Any]], threshold: float = 0.3) -> list[RecommendationDict]:
    return compute_recommendations(
        segments, _EMB, _HARD, _SEG_DATA, _SW, _LABELS, threshold
    )


def test_recommend_ranks_other_line_top() -> None:
    # chunk3 (= 混入) は割当が SPEAKER_00 だが [0,1] なので SPEAKER_01 が1位。
    out = _rec([{"start": 3.0, "end": 4.0, "speaker": "SPEAKER_00"}])
    cands = out[0]["candidates"]
    assert cands[0]["cluster"] == "SPEAKER_01"
    assert cands[0]["score"] > cands[1]["score"]
    assert out[0]["novel"] is False  # 似たラインがある → 新規ではない


def test_recommend_novel_when_below_threshold() -> None:
    # τ を 1.5 に上げれば全候補が下回り novel=True。
    out = _rec([{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}], threshold=1.5)
    assert out[0]["novel"] is True


def test_boundary_within_delta() -> None:
    # margin が 0〜δ に入るよう δ を大きめに取り、わずかに正のケースを boundary に。
    # chunk0 の s_own=0.633, s_other=0 → margin 0.633。δ=0.7 なら boundary。
    out = _run([{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}], delta=0.7)
    assert out[0]["label"] == "boundary"


def test_recompute_signals_name_based_with_mixed_names() -> None:
    """recompute_signals: 現在の話者名で centroid を作り直す (リネーム名・混在もOK)。"""
    from app.diarize import DiarizeGrid, recompute_signals

    grid: DiarizeGrid = {
        "embeddings": _EMB,
        "hard_clusters": _HARD,
        "seg_data": _SEG_DATA,
        "sliding_window": _SW,
        "label_mapping": _LABELS,
    }
    # 「鈴木」線 = chunk0,1 ([1,0]寄り)。「田中」線 = chunk2 ([0,1])。
    # 末尾 seg (chunk3 = [0,1]) は誤って「鈴木」に置かれている → 田中が近い = intruder。
    segs = [
        {"start": 0.0, "end": 1.0, "speaker": "鈴木"},
        {"start": 1.0, "end": 2.0, "speaker": "鈴木"},
        {"start": 2.0, "end": 3.0, "speaker": "田中"},
        {"start": 3.0, "end": 4.0, "speaker": "鈴木"},
    ]
    susp, rec = recompute_signals(segs, grid, suspicion_delta=0.05, recommend_threshold=0.3)
    # gid ではなく現在名で候補が返る
    assert {c["cluster"] for c in rec[3]["candidates"]} == {"鈴木", "田中"}
    assert rec[3]["candidates"][0]["cluster"] == "田中"  # 田中が最も近い
    assert susp[3]["label"] == "intruder"
    assert susp[3]["nearest"] == "田中"
    assert susp[0]["label"] == "ok"  # chunk0 は鈴木の純粋な代表
