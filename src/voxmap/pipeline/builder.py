from typing import Any

from voxmap.pipeline.default import DefaultPipeline
from voxmap.registry import get_clustering, get_embedder, get_vad


def build_pipeline(config: dict[str, Any]) -> DefaultPipeline:
    vad_cfg = config["vad"]
    emb_cfg = config["embedding"]
    clu_cfg = config["clustering"]
    return DefaultPipeline(
        vad=get_vad(vad_cfg["name"], **(vad_cfg.get("params") or {})),
        embedder=get_embedder(emb_cfg["name"], **(emb_cfg.get("params") or {})),
        clustering=get_clustering(clu_cfg["name"], **(clu_cfg.get("params") or {})),
    )
