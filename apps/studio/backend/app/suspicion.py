"""segment 粒度の怪しさ判定 (設計 §4.2 の段階0 を「他クラスタとも比較」へ拡張)。

ギャラリ不使用・**auto クラスタ重心だけ**で、混同していそうな segment を炙り出す。
レコメンドはしない (どの既知話者かは出さない)。

スコアラは当面 **生 cos** で統一 (AS-norm は未配線)。各 segment について:

    s_own   = cos(emb_seg, centroid_own)        # 自クラスタへの近さ (leave-one-out)
    s_other = max_{k≠own} cos(emb_seg, centroid_k)   # 一番近い別クラスタ
    margin  = s_own - s_other

判定 (margin 中心。intruder は閾値フリー、boundary だけ δ が要る):
    intruder : margin < 0        別クラスタの方が近い = 混入の疑い (最強)
    boundary : 0 ≤ margin < δ    端っこ・拮抗
    ok       : margin ≥ δ        問題なし

margin の差分は「同じ emb_seg から出した2スコアの引き算」なので、生 cos の
話者ごとのスケール癖がほぼ相殺される (intruder/boundary は cos でも頑健)。

埋め込みは (chunk × local_speaker) 単位なので、各出力 segment の時間窓に重なり
かつ同クラスタの (chunk, local_speaker) を集めて平均し、segment の代表ベクトルを作る。
leave-one-out: 自クラスタ重心から、その segment を構成する (chunk, local_speaker)
ベクトルを除いて算出する (混入 segment の自己引力を除くため、特に小クラスタで効く)。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict

import numpy as np
from numpy.typing import NDArray

SuspicionLabel = Literal["intruder", "boundary", "ok"]


class SuspicionDict(TypedDict):
    label: SuspicionLabel
    margin: float | None  # None = 判定不能 (該当埋め込み無し or 単一クラスタ)
    nearest: str | None  # intruder/boundary のとき「一番近い別クラスタ」の SPEAKER_xx


class CandidateDict(TypedDict):
    cluster: str  # 候補の auto クラスタ (SPEAKER_xx)。フロントが現在ラベルへ翻訳する。
    score: float  # emb_seg との cos


class RecommendationDict(TypedDict):
    # 現在の全話者ライン (auto クラスタ重心) への cos を降順に並べた候補。自クラスタも含む。
    candidates: list[CandidateDict]
    # 最良候補が τ 未満 = どのラインにも似ていない (新規話者の受け皿)。
    novel: bool


def _cos(a: NDArray[Any], b: NDArray[Any]) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _segment_members(
    start: float,
    end: float,
    gid: int,
    hard_clusters: NDArray[np.int_],
    seg_data: NDArray[np.float32],
    sw_start: float,
    sw_step: float,
    sw_duration: float,
) -> list[tuple[int, int]]:
    """segment [start,end] を構成する (chunk, local_speaker) を返す。

    条件: hard_clusters[c,s]==gid かつ chunk c が時間的に重なり かつ s が
    [start,end] 内のフレームで活性 (segmentation > 0)。
    """
    num_chunks, num_frames, _ = seg_data.shape
    members: list[tuple[int, int]] = []
    for c in range(num_chunks):
        c_start = sw_start + c * sw_step
        c_end = c_start + sw_duration
        if c_start >= end or c_end <= start:  # 時間的に重ならない
            continue
        # この chunk 内で [start,end] に入るフレーム
        frame_t = c_start + np.linspace(0.0, sw_duration, num_frames, endpoint=False)
        in_seg = (frame_t >= start) & (frame_t < end)
        if not in_seg.any():
            continue
        for s in range(hard_clusters.shape[1]):
            if int(hard_clusters[c, s]) != gid:
                continue
            active = seg_data[c, in_seg, s]
            active = active[~np.isnan(active)]
            if active.size and float(active.sum()) > 0.0:
                members.append((c, s))
    return members


def _cluster_stats(
    embeddings: NDArray[np.float32],
    hard_clusters: NDArray[np.int_],
    gids: list[int],
) -> tuple[dict[int, NDArray[np.float32]], dict[int, int], dict[int, NDArray[Any]]]:
    """クラスタごとに active (非NaN) 埋め込みの sum / count / 重心を返す。"""
    dim = embeddings.shape[-1]
    csum: dict[int, NDArray[np.float32]] = {g: np.zeros(dim, np.float32) for g in gids}
    cnt: dict[int, int] = dict.fromkeys(gids, 0)
    num_chunks, num_speakers = hard_clusters.shape
    for c in range(num_chunks):
        for s in range(num_speakers):
            g = int(hard_clusters[c, s])
            if g not in csum:
                continue
            v = embeddings[c, s]
            if np.isnan(v).any():
                continue
            csum[g] += v
            cnt[g] += 1
    centroid = {g: (csum[g] / cnt[g]) for g in gids if cnt[g] > 0}
    return csum, cnt, centroid


def _segment_emb(
    seg: Mapping[str, Any],
    gid: int,
    hard_clusters: NDArray[np.int_],
    embeddings: NDArray[np.float32],
    seg_data: NDArray[np.float32],
    sw_start: float,
    sw_step: float,
    sw_duration: float,
) -> tuple[NDArray[np.float32] | None, NDArray[np.float32] | None]:
    """segment の代表ベクトル (構成 (chunk,local) 埋め込みの平均) と構成ベクトル束。"""
    members = _segment_members(
        float(seg["start"]), float(seg["end"]), gid,
        hard_clusters, seg_data, sw_start, sw_step, sw_duration,
    )
    if not members:
        return None, None
    member_vecs = np.stack([embeddings[c, s] for c, s in members])
    return member_vecs.mean(axis=0), member_vecs


def compute_recommendations(
    segments: Sequence[Mapping[str, Any]],
    embeddings: NDArray[np.float32],
    hard_clusters: NDArray[np.int_],
    seg_data: NDArray[np.float32],
    sliding_window: Any,
    label_mapping: dict[int, str],
    threshold: float,
) -> list[RecommendationDict]:
    """各 segment の候補 = 現在の全話者ライン (auto クラスタ重心) への cos 降順 + novel。

    候補集合は「今この音声にいる話者ライン」。会議横断のグローバル gallery とは別物
    (session 内の付け替え用)。怪しさ判定と同じ emb_seg・重心・生 cos を使う。
    """
    inv_map = {label: gid for gid, label in label_mapping.items()}
    sw_start = float(sliding_window.start)
    sw_step = float(sliding_window.step)
    sw_duration = float(sliding_window.duration)
    gids = sorted(label_mapping)
    _, _, centroid = _cluster_stats(embeddings, hard_clusters, gids)

    out: list[RecommendationDict] = []
    for seg in segments:
        gid = inv_map.get(str(seg["speaker"]))
        if gid is None:
            out.append({"candidates": [], "novel": True})
            continue
        emb_seg, _ = _segment_emb(
            seg, gid, hard_clusters, embeddings, seg_data, sw_start, sw_step, sw_duration
        )
        if emb_seg is None:
            out.append({"candidates": [], "novel": True})
            continue
        cands: list[CandidateDict] = [
            {"cluster": label_mapping[g], "score": _cos(emb_seg, centroid[g])}
            for g in gids
            if g in centroid
        ]
        cands.sort(key=lambda p: p["score"], reverse=True)
        best = cands[0]["score"] if cands else -2.0
        out.append({"candidates": cands, "novel": best < threshold})
    return out


def _window_member_vecs(
    start: float,
    end: float,
    embeddings: NDArray[np.float32],
    seg_data: NDArray[np.float32],
    sw_start: float,
    sw_step: float,
    sw_duration: float,
) -> NDArray[np.float32] | None:
    """窓 [start,end] に active な (chunk, local_speaker) セルの埋め込み束を返す。

    `_segment_members` と違い **クラスタ (gid) で絞らない**。編集追従では「現在の話者名」で
    グルーピングするため、その窓に在る音響内容を素直に拾う (gid は分離時のもので当てにならない)。
    """
    num_chunks, num_frames, num_speakers = seg_data.shape
    vecs: list[NDArray[np.float32]] = []
    for c in range(num_chunks):
        c_start = sw_start + c * sw_step
        c_end = c_start + sw_duration
        if c_start >= end or c_end <= start:
            continue
        frame_t = c_start + np.linspace(0.0, sw_duration, num_frames, endpoint=False)
        in_seg = (frame_t >= start) & (frame_t < end)
        if not in_seg.any():
            continue
        for s in range(num_speakers):
            active = seg_data[c, in_seg, s]
            active = active[~np.isnan(active)]
            if active.size and float(active.sum()) > 0.0:
                v = embeddings[c, s]
                if not np.isnan(v).any():
                    vecs.append(v)
    if not vecs:
        return None
    return np.stack(vecs)


def compute_signals_by_name(
    segments: Sequence[Mapping[str, Any]],
    embeddings: NDArray[np.float32],
    seg_data: NDArray[np.float32],
    sliding_window: Any,
    delta: float,
    threshold: float,
) -> tuple[list[SuspicionDict], list[RecommendationDict]]:
    """編集追従の再計算 (名前ベース)。**現在の話者名で centroid を作り直す**。

    一括対応・マージ・手動付け替え後でも、いま各 segment に付いている話者名だけで
    完結する (gid/エイリアス不要)。`SPEAKER_00` と `田中` の混在もそのまま扱える。
    再埋め込みはせず、保持グリッドのセルを選び直して平均するだけ。
    """
    sw_start = float(sliding_window.start)
    sw_step = float(sliding_window.step)
    sw_duration = float(sliding_window.duration)
    dim = embeddings.shape[-1]

    # pass 1: segment ごとの member 束 + emb_seg、話者名ごとに sum/count を貯める
    members: list[NDArray[np.float32] | None] = []
    emb_segs: list[NDArray[np.float32] | None] = []
    name_sum: dict[str, NDArray[np.float32]] = {}
    name_cnt: dict[str, int] = {}
    for seg in segments:
        mv = _window_member_vecs(
            float(seg["start"]), float(seg["end"]),
            embeddings, seg_data, sw_start, sw_step, sw_duration,
        )
        members.append(mv)
        if mv is None:
            emb_segs.append(None)
            continue
        emb_segs.append(mv.mean(axis=0))
        name = str(seg["speaker"])
        name_sum[name] = name_sum.get(name, np.zeros(dim, np.float32)) + mv.sum(axis=0)
        name_cnt[name] = name_cnt.get(name, 0) + mv.shape[0]

    names = sorted(name_sum)
    centroid = {n: (name_sum[n] / name_cnt[n]) for n in names}

    susp: list[SuspicionDict] = []
    rec: list[RecommendationDict] = []
    for seg, mv, emb_seg in zip(segments, members, emb_segs, strict=True):
        if emb_seg is None or mv is None:  # 窓に音響が無い (無音/未検出) → 判定不能
            susp.append({"label": "ok", "margin": None, "nearest": None})
            rec.append({"candidates": [], "novel": True})
            continue
        cands: list[CandidateDict] = [
            {"cluster": n, "score": _cos(emb_seg, centroid[n])} for n in names
        ]
        cands.sort(key=lambda p: p["score"], reverse=True)
        best = cands[0]["score"] if cands else -2.0
        rec.append({"candidates": cands, "novel": best < threshold})

        own = str(seg["speaker"])
        # 自名 centroid は leave-one-out (この segment のセルを除く) で自己引力を除く
        loo_sum = name_sum[own] - mv.sum(axis=0)
        loo_n = name_cnt[own] - mv.shape[0]
        own_centroid = (loo_sum / loo_n) if loo_n > 0 else centroid[own]
        s_own = _cos(emb_seg, own_centroid)
        s_other = -2.0
        nearest: str | None = None
        for n in names:
            if n == own:
                continue
            sim = _cos(emb_seg, centroid[n])
            if sim > s_other:
                s_other = sim
                nearest = n
        if nearest is None:  # 単一話者しかいない → 比較対象なし
            susp.append({"label": "ok", "margin": None, "nearest": None})
            continue
        margin = s_own - s_other
        if margin < 0.0:
            label: SuspicionLabel = "intruder"
        elif margin < delta:
            label = "boundary"
        else:
            label = "ok"
        susp.append({
            "label": label,
            "margin": float(margin),
            "nearest": nearest if label != "ok" else None,
        })
    return susp, rec


def compute_suspicion(
    segments: Sequence[Mapping[str, Any]],
    embeddings: NDArray[np.float32],
    hard_clusters: NDArray[np.int_],
    seg_data: NDArray[np.float32],
    sliding_window: Any,
    label_mapping: dict[int, str],
    delta: float,
) -> list[SuspicionDict]:
    """各 segment の怪しさを返す (segments と同順)。

    embeddings: (C, S, D)  hard_clusters: (C, S)  seg_data: (C, F, S)
    label_mapping: {global_id -> "SPEAKER_xx"}
    """
    inv_map = {label: gid for gid, label in label_mapping.items()}
    sw_start = float(sliding_window.start)
    sw_step = float(sliding_window.step)
    sw_duration = float(sliding_window.duration)

    # クラスタごとに active (非NaN) 埋め込みの sum / count を貯める (重心 + leave-one-out 用)
    gids = sorted(label_mapping)
    dim = embeddings.shape[-1]
    csum: dict[int, NDArray[np.float32]] = {g: np.zeros(dim, np.float32) for g in gids}
    cnt: dict[int, int] = dict.fromkeys(gids, 0)
    num_chunks, num_speakers = hard_clusters.shape
    for c in range(num_chunks):
        for s in range(num_speakers):
            g = int(hard_clusters[c, s])
            if g not in csum:
                continue
            v = embeddings[c, s]
            if np.isnan(v).any():
                continue
            csum[g] += v
            cnt[g] += 1

    centroid = {g: (csum[g] / cnt[g]) for g in gids if cnt[g] > 0}

    out: list[SuspicionDict] = []
    for seg in segments:
        speaker = str(seg["speaker"])
        gid = inv_map.get(speaker)
        if gid is None or gid not in centroid:
            out.append({"label": "ok", "margin": None, "nearest": None})
            continue
        members = _segment_members(
            float(seg["start"]), float(seg["end"]), gid,
            hard_clusters, seg_data, sw_start, sw_step, sw_duration,
        )
        if not members:
            out.append({"label": "ok", "margin": None, "nearest": None})
            continue

        member_vecs = np.stack([embeddings[c, s] for c, s in members])
        emb_seg = member_vecs.mean(axis=0)

        # leave-one-out: 自クラスタ重心から segment 構成ベクトルを除く
        loo_sum = csum[gid] - member_vecs.sum(axis=0)
        loo_n = cnt[gid] - len(members)
        centroid_own = (loo_sum / loo_n) if loo_n > 0 else centroid[gid]
        s_own = _cos(emb_seg, centroid_own)

        # 一番近い別クラスタ
        s_other = -2.0
        nearest: str | None = None
        for g in gids:
            if g == gid or g not in centroid:
                continue
            sim = _cos(emb_seg, centroid[g])
            if sim > s_other:
                s_other = sim
                nearest = label_mapping[g]
        if nearest is None:  # 単一クラスタ → 比較対象なし
            out.append({"label": "ok", "margin": None, "nearest": None})
            continue

        margin = s_own - s_other
        if margin < 0.0:
            label: SuspicionLabel = "intruder"
        elif margin < delta:
            label = "boundary"
        else:
            label = "ok"
        out.append({
            "label": label,
            "margin": float(margin),
            "nearest": nearest if label != "ok" else None,
        })
    return out
