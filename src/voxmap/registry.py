from typing import Any

from voxmap.asr.base import ASR
from voxmap.embedding.base import Embedder
from voxmap.scorer.base import SpeakerScorer
from voxmap.vad.base import VAD


def get_vad(name: str, **kwargs: Any) -> VAD:
    if name == "pyannote":
        from voxmap.vad.pyannote_vad import PyannoteVAD

        return PyannoteVAD(**kwargs)
    raise ValueError(f"Unknown VAD: {name!r}")


def get_embedder(name: str, **kwargs: Any) -> Embedder:
    if name == "pyannote":
        from voxmap.embedding.pyannote_emb import PyannoteEmbedder

        return PyannoteEmbedder(**kwargs)
    raise ValueError(f"Unknown embedder: {name!r}")


def get_segmenter(name: str, **kwargs: Any) -> Any:
    """Powerset chunk segmenter (PyanNet-style). Distinct from VAD."""
    if name == "pyannet":
        from voxmap.segmentation.pyannet_seg import load_pyannet_segmenter

        return load_pyannet_segmenter(**kwargs)
    raise ValueError(f"Unknown segmenter: {name!r}")


def get_chunk_embedder(name: str, **kwargs: Any) -> Any:
    """Chunk-level embedder for the diarization-3.1 flow.

    Different signature from `get_embedder` (which takes flat segments).
    """
    if name == "wespeaker":
        from voxmap.embedding.wespeaker_emb import load_wespeaker_embedder

        return load_wespeaker_embedder(**kwargs)
    if name == "campplus":
        from voxmap.embedding.wespeaker_emb import load_campplus_embedder

        return load_campplus_embedder(**kwargs)
    raise ValueError(f"Unknown chunk embedder: {name!r}")


def get_clustering(name: str, **kwargs: Any) -> Any:
    if name == "ahc":
        from voxmap.clustering.ahc import AHC

        return AHC(**kwargs)
    raise ValueError(f"Unknown clustering: {name!r}")


def get_scorer(name: str, **kwargs: Any) -> SpeakerScorer:
    """Speaker-similarity scorer for enrollment-based recommendation (open-set ASV)."""
    if name == "cos":
        from voxmap.scorer.cos import CosScorer

        return CosScorer(**kwargs)
    if name == "as-norm":
        from voxmap.scorer.as_norm import ASNormScorer

        return ASNormScorer(**kwargs)
    raise ValueError(f"Unknown scorer: {name!r}")


def get_asr(name: str, **kwargs: Any) -> ASR:
    if name == "parakeet":
        from voxmap.asr.parakeet import ParakeetASR

        return ParakeetASR(**kwargs)
    raise ValueError(f"Unknown ASR: {name!r}")
