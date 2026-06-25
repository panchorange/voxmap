"""Reusable visualization + diagnostics for a diarization pipeline's internals.

Per-analysis `analysis/<id>/analyze.py` and the `scripts/analyze_pipeline.py`
CLI both import these helpers, so the figures and cluster metrics they produce
are computed *the same way* everywhere — and, crucially, with the **production
AHC** (`pipeline.clustering`) rather than a hand-rolled copy. That parity is the
whole point: when diagnosing why a config (e.g. coarse stride) hurts DER, the
dendrogram / clusters shown must be the ones the pipeline actually cut.

Capture relies on the pipeline `hook` mechanism, which yields three intermediates
(see voxmap.pipeline.diarization31): `segmentation`, `speaker_counting`,
`embeddings`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torchaudio  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from pyannote.core import Annotation, SlidingWindowFeature  # noqa: E402
from scipy.cluster.hierarchy import dendrogram  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402

from voxmap.clustering.ahc import AHC  # noqa: E402
from voxmap.types import Audio, Diarization  # noqa: E402

Segments = list[tuple[str, float, float]]


def _palette(n: int = 10) -> list[Any]:
    """Discrete colour list, avoiding `plt.cm.tab10.colors` (untyped attribute)."""
    cmap = plt.get_cmap("tab10" if n <= 10 else "tab20")
    return [cmap(i) for i in range(min(n, 10) if n <= 10 else 20)]


# ---------- capture ----------


def load_audio(path: str | Path) -> Audio:
    waveform, sr = torchaudio.load(str(path))
    return Audio(waveform=waveform, sample_rate=sr)


def run_with_hooks(pipeline: Any, audio: Audio, uri: str) -> dict[str, Any]:
    """Run the pipeline, capturing intermediates via its hook.

    Returns a dict with `segmentation`, `speaker_counting`, `embeddings`
    (the last non-None payload per step) plus the final `annotation`.
    """
    captured: dict[str, Any] = {}

    def hook(step: str, data: Any, **_kwargs: Any) -> None:
        if data is not None:  # segmenter also calls the hook with progress=None
            captured[step] = data

    annotation = pipeline(audio, uri=uri, hook=hook)
    captured["annotation"] = annotation
    return captured


# ---------- reference-speaker assignment ----------


def assign_ref_speakers(
    segmentations: SlidingWindowFeature,
    chunk_idx: np.ndarray,
    speaker_idx: np.ndarray,
    reference: Diarization,
) -> tuple[np.ndarray, dict[str, int]]:
    """For each filtered embedding, the reference speaker with max time overlap.

    Returns (labels, label_to_int) where label_to_int maps each ref speaker (and
    "<no_ref>") to a stable colour index ordered by total speaking time.
    """
    cw = segmentations.sliding_window
    chunk_data = segmentations.data
    num_frames = chunk_data.shape[1]
    frame_dur = cw.duration / num_frames

    ref_by_spk: dict[str, list[tuple[float, float]]] = {}
    for t in reference.turns:
        ref_by_spk.setdefault(t.speaker, []).append((t.segment.start, t.segment.end))
    speakers_sorted = sorted(ref_by_spk, key=lambda s: -sum(e - st for st, e in ref_by_spk[s]))

    labels: list[str] = []
    for c, s in zip(chunk_idx, speaker_idx, strict=True):
        chunk_start = cw.start + c * cw.step
        active = chunk_data[c, :, s] > 0
        if not active.any():
            labels.append("<no_ref>")
            continue
        d = np.diff(active.astype(np.int8))
        starts = (np.where(d == 1)[0] + 1).tolist()
        ends = (np.where(d == -1)[0] + 1).tolist()
        if active[0]:
            starts.insert(0, 0)
        if active[-1]:
            ends.append(len(active))
        intervals = [
            (chunk_start + a * frame_dur, chunk_start + b * frame_dur)
            for a, b in zip(starts, ends, strict=True)
        ]
        best_spk, best_ov = "<no_ref>", 0.0
        for spk in speakers_sorted:
            ov = 0.0
            for ts, te in ref_by_spk[spk]:
                for as_, ae in intervals:
                    ov += max(0.0, min(te, ae) - max(ts, as_))
            if ov > best_ov:
                best_ov = ov
                best_spk = spk
        labels.append(best_spk)

    label_to_int = {spk: i for i, spk in enumerate(speakers_sorted)}
    label_to_int["<no_ref>"] = len(speakers_sorted)
    return np.array(labels), label_to_int


# ---------- metrics ----------


def cluster_metrics(
    seg_labels: np.ndarray, ref_labels: np.ndarray, n_pred: int, n_ref: int
) -> dict[str, Any]:
    """Quantify the clustering against the reference labelling of each segment.

    cluster_purity: weighted fraction of segments assigned to their predicted
    cluster's majority reference speaker (1.0 = every cluster is pure).
    """
    total = int(len(seg_labels))
    purity = 0.0
    if total:
        for c in np.unique(seg_labels):
            refs_in = ref_labels[seg_labels == c]
            _, counts = np.unique(refs_in, return_counts=True)
            purity += int(counts.max())
        purity /= total
    return {
        "n_speakers_pred": int(n_pred),
        "n_speakers_ref": int(n_ref),
        "count_error": int(n_pred - n_ref),
        # number of clusters AHC actually produced on the filtered embeddings.
        # distinct from n_speakers_pred (the final annotation's speaker count): when
        # re-clustering cached embeddings, the final annotation is *not* recomputed,
        # so this is the metric that responds to clustering-param changes.
        "n_clusters": int(len(np.unique(seg_labels))) if total else 0,
        "n_segments": total,
        "cluster_purity": round(float(purity), 4),
    }


# ---------- timeline plot ----------


def annot_segments(obj: Annotation | Diarization) -> Segments:
    """Unify pyannote.Annotation and voxmap.Diarization into [(label, start, end)]."""
    if isinstance(obj, Annotation):
        return [
            (str(lab), float(seg.start), float(seg.end))
            for seg, _, lab in obj.itertracks(yield_label=True)
        ]
    return [(str(t.speaker), float(t.segment.start), float(t.segment.end)) for t in obj.turns]


def _speaker_rows(segments: Segments) -> list[tuple[str, list[tuple[float, float]]]]:
    rows: dict[str, list[tuple[float, float]]] = {}
    for lab, s, e in segments:
        rows.setdefault(lab, []).append((s, e - s))
    return sorted(rows.items(), key=lambda kv: -sum(d for _, d in kv[1]))


def _draw_timeline(
    ax: Axes,
    rows: list[tuple[str, list[tuple[float, float]]]],
    title: str,
    total_t: float,
    palette: list[Any],
) -> None:
    ax.set_title(title, fontsize=10, loc="left")
    for i, (lab, segs) in enumerate(rows):
        color = palette[i % len(palette)]
        for s, d in segs:
            ax.add_patch(Rectangle((s, i - 0.4), d, 0.8, facecolor=color, edgecolor="none"))
        ax.text(-total_t * 0.005, i, lab, ha="right", va="center", fontsize=7)
    ax.set_xlim(0, total_t)
    ax.set_ylim(-0.6, max(len(rows) - 0.4, 0.4))
    ax.set_yticks([])
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)


def plot_segmentation_timeline(
    meeting: str,
    annotation: Annotation,
    reference: Diarization,
    count: SlidingWindowFeature,
    out_path: str | Path,
) -> None:
    """Reference vs predicted speaker timelines + instantaneous speaker count."""
    pred_segs = annot_segments(annotation)
    ref_segs = annot_segments(reference)
    total_t = max(
        max((e for _, _, e in pred_segs), default=0.0),
        max((e for _, _, e in ref_segs), default=0.0),
    )
    ref_rows = _speaker_rows(ref_segs)
    pred_rows = _speaker_rows(pred_segs)
    palette = _palette(10)

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(14, 5.5),
        gridspec_kw={"height_ratios": [max(len(ref_rows), 1), max(len(pred_rows), 1), 2]},
        constrained_layout=True,
    )
    fig.suptitle(f"{meeting}", fontsize=12)
    _draw_timeline(axes[0], ref_rows, f"Reference ({len(ref_rows)} speakers)", total_t, palette)
    _draw_timeline(axes[1], pred_rows, f"Predicted ({len(pred_rows)} speakers)", total_t, palette)

    sw = count.sliding_window
    times = sw.start + sw.step * np.arange(len(count.data))
    axes[2].plot(times, np.asarray(count.data).ravel(), color="steelblue", linewidth=0.8)
    axes[2].set_title("Instantaneous speaker count (from segmentation)", fontsize=10, loc="left")
    axes[2].set_xlabel("time (s)")
    axes[2].set_ylabel("count")
    axes[2].set_xlim(0, total_t)
    axes[2].set_ylim(0, max(float(np.nanmax(count.data)) + 0.5, 1.5))
    axes[2].grid(True, alpha=0.3)

    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# ---------- cluster diagnostics plot ----------


def plot_cluster_diagnostics(
    meeting: str,
    emb_filtered: np.ndarray,
    seg_labels: np.ndarray,
    ref_labels: np.ndarray,
    ref_label_to_int: dict[str, int],
    linkage_z: np.ndarray,
    threshold: float,
    n_pred: int,
    n_ref: int,
    out_path: str | Path,
) -> None:
    """4-panel: cosine-sim matrix, dendrogram@threshold, PCA by predicted, PCA by ref."""
    normed = emb_filtered / np.linalg.norm(emb_filtered, axis=-1, keepdims=True)
    n_final = len(np.unique(seg_labels))

    fig, axes = plt.subplots(1, 4, figsize=(22, 5), constrained_layout=True)
    fig.suptitle(
        f"{meeting}  |  n_segments={len(normed)}  predicted {n_pred} / reference {n_ref}",
        fontsize=12,
    )

    # 1) cosine similarity matrix sorted by predicted cluster
    ax = axes[0]
    order = np.argsort(seg_labels)
    sim = normed[order] @ normed[order].T
    im = ax.imshow(sim, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    boundaries = np.where(np.diff(seg_labels[order]))[0] + 1
    for b in boundaries:
        ax.axhline(y=b - 0.5, color="black", linewidth=0.7)
        ax.axvline(x=b - 0.5, color="black", linewidth=0.7)
    ax.set_title("Cosine sim (sorted by predicted cluster)", fontsize=10, loc="left")
    ax.set_xlabel("segment idx")
    ax.set_ylabel("segment idx")
    fig.colorbar(im, ax=ax, shrink=0.7)

    # 2) dendrogram with threshold line
    ax = axes[1]
    dendrogram(linkage_z, ax=ax, no_labels=True, color_threshold=threshold)
    ax.axhline(
        y=threshold,
        color="red",
        linestyle="--",
        linewidth=1.2,
        label=f"threshold = {threshold:.4f}",
    )
    ax.set_title("Dendrogram (production AHC linkage)", fontsize=10, loc="left")
    ax.set_ylabel("euclidean distance")
    ax.legend(loc="upper right", fontsize=9)

    pca = PCA(n_components=2)
    proj = pca.fit_transform(normed)
    palette = _palette(10)

    # 3) PCA coloured by predicted cluster (size-desc for stable cluster_0..)
    ax = axes[2]
    pred_cmap = plt.get_cmap("tab10" if n_final <= 10 else "tab20")
    pred_mod = 10 if n_final <= 10 else 20
    pred_unique, pred_counts = np.unique(seg_labels, return_counts=True)
    for rank, cid in enumerate(pred_unique[np.argsort(-pred_counts)]):
        mask = seg_labels == cid
        color = pred_cmap(rank % pred_mod)
        ax.scatter(
            proj[mask, 0],
            proj[mask, 1],
            c=[color],
            s=18,
            alpha=0.75,
            label=f"cluster_{rank} (n={int(mask.sum())})",
        )
    ax.set_title(f"PCA 2D — predicted cluster ({n_final})", fontsize=10, loc="left")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%})")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%})")
    ax.legend(loc="best", fontsize=7, framealpha=0.85)
    ax.grid(True, alpha=0.3)

    # 4) PCA coloured by reference speaker
    ax = axes[3]
    for lbl in [x for x in ref_label_to_int if (ref_labels == x).any()]:
        mask = ref_labels == lbl
        color = (0.6, 0.6, 0.6, 1.0) if lbl == "<no_ref>" else palette[ref_label_to_int[lbl] % 10]
        ax.scatter(
            proj[mask, 0],
            proj[mask, 1],
            c=[color],
            s=18,
            alpha=0.75,
            label=f"{lbl} (n={int(mask.sum())})",
        )
    ax.set_title(f"PCA 2D — reference speaker ({n_ref})", fontsize=10, loc="left")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%})")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%})")
    ax.legend(loc="best", fontsize=7, framealpha=0.85)
    ax.grid(True, alpha=0.3)

    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# ---------- high-level driver ----------


def diagnose_meeting(
    pipeline: Any,
    audio: Audio,
    reference: Diarization,
    uri: str,
    out_dir: str | Path,
    captured: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture intermediates, cluster with the production AHC, plot, return metrics.

    Pass `captured` (from a previous `run_with_hooks`) to skip re-running the
    pipeline. Writes `<uri>_timeline.png` and `<uri>_cluster.png` into `out_dir`.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if captured is None:
        captured = run_with_hooks(pipeline, audio, uri)
    embeddings = captured["embeddings"]
    segmentations = captured["segmentation"]
    count = captured["speaker_counting"]
    annotation = captured["annotation"]

    ahc: AHC = pipeline.clustering
    emb_f, chunk_idx, speaker_idx = AHC._filter_embeddings(embeddings, segmentations)
    hard, _soft, _centroids = ahc(embeddings, segmentations)
    seg_labels = hard[chunk_idx, speaker_idx]
    linkage_z = AHC.compute_linkage(emb_f, method=ahc.method, metric=ahc.metric)
    ref_labels, ref_l2i = assign_ref_speakers(segmentations, chunk_idx, speaker_idx, reference)

    n_ref = len(reference.speakers)
    n_pred = len(set(annotation.labels()))

    plot_segmentation_timeline(uri, annotation, reference, count, out_dir / f"{uri}_timeline.png")
    plot_cluster_diagnostics(
        uri,
        emb_f,
        seg_labels,
        ref_labels,
        ref_l2i,
        linkage_z,
        ahc.threshold,
        n_pred,
        n_ref,
        out_dir / f"{uri}_cluster.png",
    )
    return cluster_metrics(seg_labels, ref_labels, n_pred, n_ref)
