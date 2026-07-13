from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import torch
import yaml

from voxmap.pipeline.diarization31 import Diarization31Pipeline, load_diarization31_pipeline


def resolve_device(name: str) -> torch.device:
    """'auto' は cuda > mps > cpu の順でフォールバック。それ以外はそのまま解釈。"""
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def build_pipeline(config: str | Path | dict[str, Any]) -> Diarization31Pipeline:
    """speaker-diarization-3.1 パイプラインを YAML config (パス or dict) から組み立てる。

    voxmap-studio と同一エンジン (`load_diarization31_pipeline`) を使う。config は
    `pipeline:` ブロックに `load_diarization31_pipeline` の引数を持つ (configs/pipeline/
    baseline.yaml 参照)。HF gated モデルのトークンは環境変数 `HF_TOKEN` から拾う。
    """
    if isinstance(config, dict):
        cfg: dict[str, Any] = config
    else:
        with Path(config).open() as f:
            cfg = yaml.safe_load(f)

    p = cfg["pipeline"]
    device = resolve_device(str(p.get("device", "auto")))
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
