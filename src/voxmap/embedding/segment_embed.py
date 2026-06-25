"""Per-segment (turn) embedding by reusing the diarization embedding model.

The 3.1 pipeline embeds (chunk x local-speaker) pairs and discards the result
after clustering. The annotation recommender instead needs ONE vector per output
turn (the unit a user clicks). This re-embeds each turn with the SAME model the
clustering used — `weights=None` makes StatsPool average-pool over the whole crop
— so per-turn vectors live in the same space as the clustering centroids
(design 4.1). Without that, enrollment/suspicion scores would compare across
mismatched spaces.

Variable-length turns are embedded one at a time; batching (pad-to-max) is a
future optimization — turn counts per meeting are modest.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import torch
import torch.nn.functional as F
from numpy.typing import NDArray

from voxmap.embedding.wespeaker_emb import _crop_padded
from voxmap.types import Audio, Segment


class PoolableModel(Protocol):
    """Minimal WeSpeaker-compatible surface: waveform + optional frame weights."""

    def __call__(
        self, waveform: torch.Tensor, weights: torch.Tensor | None = None
    ) -> torch.Tensor: ...


@torch.inference_mode()
def embed_segments(
    model: PoolableModel,
    audio: Audio,
    segments: list[Segment],
    device: torch.device | None = None,
    min_samples: int = 0,
    batch_size: int = 32,
) -> NDArray[np.float32]:
    """Return (len(segments), dim) embeddings, one per segment.

    weights=None -> uniform pooling over the full crop = "embed this whole turn".

    Turns are batched (one forward per `batch_size`, not per turn) to avoid a
    per-turn device round-trip — on MPS the per-call sync dominates otherwise.
    Crops are length-sorted so intra-batch zero-padding (and its pooling
    dilution) stays minimal; outputs are returned in the original order.

    Very short turns (e.g. backchannels) can be shorter than the model's fbank
    window and crash. `min_samples` zero-pads such crops up to that floor
    (pass `model.min_num_samples`); their embeddings are unreliable but the
    suspicion layer flags them low_quality anyway.
    """
    device = device or torch.device("cpu")
    sample_rate = audio.sample_rate
    if not segments:
        return np.empty((0, 0), dtype=np.float32)

    crops: list[torch.Tensor] = []
    for seg in segments:
        crop = _crop_padded(audio.waveform, sample_rate, seg.start, seg.end)
        if crop.shape[0] > 1:  # downmix to mono (matches the chunk embedder)
            crop = crop.mean(dim=0, keepdim=True)
        if crop.shape[1] < min_samples:  # zero-pad short turns up to the fbank floor
            crop = F.pad(crop, (0, min_samples - crop.shape[1]))
        crops.append(crop)  # (1, Li)

    order = sorted(range(len(crops)), key=lambda i: crops[i].shape[1])
    results: list[tuple[int, NDArray[np.float32]]] = []
    for start in range(0, len(order), batch_size):
        idxs = order[start : start + batch_size]
        maxlen = max(crops[i].shape[1] for i in idxs)
        wavs = torch.stack(
            [F.pad(crops[i], (0, maxlen - crops[i].shape[1])) for i in idxs]
        ).to(device)  # (B, 1, maxlen)
        emb = np.asarray(model(wavs, weights=None).cpu().numpy(), dtype=np.float32)
        results.extend((i, emb[j]) for j, i in enumerate(idxs))

    results.sort(key=lambda r: r[0])
    return np.vstack([e for _, e in results]).astype(np.float32)
