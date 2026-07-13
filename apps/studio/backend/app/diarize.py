"""voxmap パイプラインのラッパ。config から Diarization31 を組み立て、音声を分離する。

依存方向: backend -> voxmap の一方向 (voxmap は backend を知らない)。
パラメータ・呼び出しは experiments の run.py の reference マッピングに揃える。
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
import torch
from numpy.typing import NDArray
from voxmap.io.audio import load_audio
from voxmap.log import get_logger
from voxmap.pipeline.diarization31 import Diarization31Pipeline, load_diarization31_pipeline

from .suspicion import (
    RecommendationDict,
    SuspicionDict,
    compute_recommendations,
    compute_signals_by_name,
    compute_suspicion,
)

log = get_logger(__name__)


class SegmentDict(TypedDict):
    start: float
    end: float
    speaker: str


class DiarizeGrid(TypedDict):
    """編集追従の再計算用に、分離が出した埋め込みグリッドを保持する。

    再埋め込みせず、編集後の窓に重なるセルを選び直して emb_seg を作り直すための材料。
    フロントには返さない (サーバ側セッションに保持し /api/recompute で使う)。
    """

    embeddings: NDArray[np.float32]  # (C, S, D)
    hard_clusters: NDArray[np.int_]  # (C, S)
    seg_data: NDArray[np.float32]  # (C, F, S)
    sliding_window: Any  # SlidingWindow (start/step/duration)
    label_mapping: dict[int, str]


class DiarizeResult(TypedDict):
    segments: list[SegmentDict]
    # auto-cluster label (SPEAKER_xx) -> centroid (D,), reused from clustering.
    # No second embedding pass: these come straight from the pipeline's AHC centroids.
    centroids: dict[str, NDArray[np.float32]]
    # segment 粒度の怪しさ判定 (segments と同順)。suspicion.compute_suspicion の出力。
    suspicion: list[SuspicionDict]
    # segment 粒度の話者候補 (segments と同順)。現在の話者ラインへの cos 降順 + novel。
    recommendation: list[RecommendationDict]
    # 編集追従の再計算用グリッド。中間配列が揃わなかったときは None。
    grid: DiarizeGrid | None


def resolve_device(name: str) -> torch.device:
    """'auto' は cuda > mps > cpu の順でフォールバック。"""
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def build_pipeline(config: dict[str, Any], device: torch.device) -> Diarization31Pipeline:
    p = config["pipeline"]
    return load_diarization31_pipeline(
        segmentation_model=str(p["segmentation_model"]),
        embedding_model=str(p["embedding_model"]),
        threshold=float(p["threshold"]),
        method=str(p["method"]),
        min_cluster_size=int(p.get("min_cluster_size", 12)),
        min_cluster_fraction=p.get("min_cluster_fraction"),
        embedding_batch_size=int(p.get("embedding_batch_size", 32)),
        segmentation_batch_size=int(p.get("segmentation_batch_size", 32)),
        embedding_exclude_overlap=bool(p.get("embedding_exclude_overlap", True)),
        min_duration_off=float(p.get("min_duration_off", 0.0)),
        min_duration_on=float(p.get("min_duration_on", 0.3)),
        segmentation_step=p.get("segmentation_step"),
        embedding_per_chunk=bool(p.get("embedding_per_chunk", False)),
        embedding_dtype=str(p.get("embedding_dtype", "float32")),
        fbank_backend=str(p.get("fbank_backend", "kaldi")),
        device=device,
        token=os.environ.get("HF_TOKEN"),
    )


def diarize_file(
    pipeline: Diarization31Pipeline,
    path: Path,
    num_speakers: int | None = None,
    suspicion_delta: float = 0.05,
    recommend_threshold: float = 0.3,
    min_duration_on: float | None = None,
) -> DiarizeResult:
    """音声ファイルを分離し、segment 一覧と auto クラスタ重心・怪しさを返す。

    重心はクラスタリングが既に算出したもの (`hook("centroids", ...)`) を拾うだけで、
    レコメンド用に segment を再埋め込みしない (設計§7 の RTF 影響なしを実現)。
    怪しさ判定も既に算出済みの embeddings / hard_clusters / segmentation を再利用するだけ。

    min_duration_on: 呼び出し単位で config デフォルト (0.3) を上書きする (範囲 [0.1, 1.0]、
    妥当性チェックは pipeline 側の ValueError に委ねる)。None ならデフォルトを使う。
    """
    audio = load_audio(path)
    audio_seconds = audio.waveform.shape[-1] / audio.sample_rate
    kwargs: dict[str, Any] = {}
    if num_speakers is not None:
        kwargs["num_speakers"] = num_speakers
    if min_duration_on is not None:
        kwargs["min_duration_on"] = min_duration_on

    centroids: dict[str, NDArray[np.float32]] = {}
    cap: dict[str, Any] = {}  # embeddings / hard_clusters / segmentation / label_mapping

    def hook(name: str, value: Any, **kw: Any) -> None:
        if name == "centroids":
            centroids.update(
                {k: np.asarray(v, dtype=np.float32) for k, v in value.items()}
            )
        elif name == "embeddings" and "completed" not in kw:
            # 進捗用の部分バッチ (completed kwarg 付き) は無視し、完全配列だけ拾う
            cap["embeddings"] = np.asarray(value, dtype=np.float32)
        elif name == "hard_clusters":
            cap["hard_clusters"] = np.asarray(value)
        elif name == "segmentation":
            cap["segmentation"] = value  # SlidingWindowFeature
        elif name == "label_mapping":
            cap["label_mapping"] = dict(value)

    start = time.perf_counter()
    annotation = pipeline(audio, hook=hook, **kwargs)
    elapsed = time.perf_counter() - start

    segments: list[SegmentDict] = [
        {"start": float(seg.start), "end": float(seg.end), "speaker": str(label)}
        for seg, _track, label in annotation.itertracks(yield_label=True)
    ]

    suspicion: list[SuspicionDict]
    recommendation: list[RecommendationDict]
    grid: DiarizeGrid | None
    if {"embeddings", "hard_clusters", "segmentation", "label_mapping"} <= cap.keys():
        seg_swf = cap["segmentation"]
        seg_data = np.asarray(seg_swf.data, dtype=np.float32)
        sw = seg_swf.sliding_window
        suspicion = compute_suspicion(
            segments, cap["embeddings"], cap["hard_clusters"],
            seg_data, sw, cap["label_mapping"], suspicion_delta,
        )
        recommendation = compute_recommendations(
            segments, cap["embeddings"], cap["hard_clusters"],
            seg_data, sw, cap["label_mapping"], recommend_threshold,
        )
        grid = {
            "embeddings": cap["embeddings"],
            "hard_clusters": cap["hard_clusters"],
            "seg_data": seg_data,
            "sliding_window": sw,
            "label_mapping": cap["label_mapping"],
        }
    else:
        suspicion = [{"label": "ok", "margin": None, "nearest": None} for _ in segments]
        recommendation = [{"candidates": [], "novel": True} for _ in segments]
        grid = None

    log.info(
        "diarize_done",
        file=path.name,
        audio_s=round(audio_seconds, 1),
        latency_s=round(elapsed, 2),
        rtf=round(elapsed / audio_seconds, 4) if audio_seconds > 0 else None,
        n_segments=len(segments),
        n_suspicious=sum(1 for s in suspicion if s["label"] != "ok"),
    )
    return {
        "segments": segments,
        "centroids": centroids,
        "suspicion": suspicion,
        "recommendation": recommendation,
        "grid": grid,
    }


def recompute_signals(
    segments: Sequence[Mapping[str, Any]],
    grid: DiarizeGrid,
    suspicion_delta: float,
    recommend_threshold: float,
) -> tuple[list[SuspicionDict], list[RecommendationDict]]:
    """編集後の segment 群に怪しさ/レコメンドを追従させる (再埋め込みなし、名前ベース)。

    いま各 segment に付いている話者名で centroid を作り直すので、一括対応・マージ・
    付け替え後 (SPEAKER_00 と 田中 の混在含む) でも追従する。gid/label_mapping 非依存。
    """
    return compute_signals_by_name(
        segments,
        grid["embeddings"],
        grid["seg_data"],
        grid["sliding_window"],
        suspicion_delta,
        recommend_threshold,
    )
