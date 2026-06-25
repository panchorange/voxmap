"""pipeline 各ステージの中間値を可視化するデバッグスクリプト。

segmentation → speaker_counting → embedding の順に、各ステージで
どんな shape / dtype / 値が渡されているかを標準出力 + matplotlib で確認する。

Usage:
    uv run python scripts/inspect_pipeline_stages.py
    uv run python scripts/inspect_pipeline_stages.py \
        --audio data/raw/ami/audio/TS3003c.Mix-Headset.wav --seconds 60
    uv run python scripts/inspect_pipeline_stages.py \
        --audio data/raw/msdwild/audio/many.val/00004.wav --stride 3
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np
import torch
import torchaudio
import typer

matplotlib.use("Agg")
import japanize_matplotlib  # noqa: F401
import matplotlib.pyplot as plt
from pyannote.core import SlidingWindowFeature

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from voxmap.pipeline.diarization31 import load_diarization31_pipeline  # noqa: E402
from voxmap.types import Audio  # noqa: E402

app = typer.Typer(add_completion=False)


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def _print_swf(name: str, swf: SlidingWindowFeature) -> None:
    """SlidingWindowFeature の詳細を印字する。"""
    d = swf.data
    sw = swf.sliding_window
    print(f"  shape    : {d.shape}  (dtype={d.dtype})")
    print(f"  window   : start={sw.start:.4f}s  duration={sw.duration:.4f}s  step={sw.step:.4f}s")
    if d.ndim == 3:
        num_chunks, num_frames, num_local_spk = d.shape
        audio_covered = sw.start + (num_chunks - 1) * sw.step + sw.duration
        print(f"  chunks   : {num_chunks}  (audio covered ≈ {audio_covered:.1f}s)")
        print(f"  frames/chunk : {num_frames}")
        print(f"  local speakers : {num_local_spk}")
        print()
        for s in range(num_local_spk):
            col = d[:, :, s]  # (chunks, frames)
            active_frames = (col > 0).sum()
            total = col.size
            print(
                f"  local_spk[{s}]: min={col.min():.3f}  max={col.max():.3f}  "
                f"mean={col.mean():.3f}  active_frames={active_frames}/{total} "
                f"({100 * active_frames / total:.1f}%)"
            )
        print()
        # 同時発話数の分布 (per frame, over all chunks)
        per_frame_count = (d > 0).sum(axis=2)  # (chunks, frames)
        flat = per_frame_count.flatten()
        for n in range(num_local_spk + 1):
            cnt = (flat == n).sum()
            print(f"  同時発話={n}の frame数: {cnt:>7d}  ({100 * cnt / flat.size:.1f}%)")
    elif d.ndim == 2:
        print(f"  shape details: {d.shape}")
        print(f"  min={d.min():.3f}  max={d.max():.3f}  mean={d.mean():.3f}")
    elif d.ndim == 1:
        print(f"  frames={d.shape[0]}")
        vals, counts = np.unique(d.astype(int), return_counts=True)
        for v, c in zip(vals, counts, strict=False):
            print(f"  count={v}: {c:>7d} frames  ({100 * c / d.size:.1f}%)")


def _print_embeddings(emb: np.ndarray) -> None:
    """embedding array (num_active, 256) の詳細を印字する。"""
    print(f"  shape    : {emb.shape}  (dtype={emb.dtype})")
    nan_mask = np.isnan(emb).any(axis=-1)
    active = (~nan_mask).sum()
    print(f"  NaN rows : {nan_mask.sum()} / {emb.shape[0]}  (active={active})")
    if active > 0:
        active_emb = emb[~nan_mask]
        norms = np.linalg.norm(active_emb, axis=-1)
        print(f"  L2 norm  : min={norms.min():.3f}  max={norms.max():.3f}  mean={norms.mean():.3f}")
        print(
            f"  value    : min={active_emb.min():.4f}  max={active_emb.max():.4f}  "
            f"mean={active_emb.mean():.4f}"
        )


def _plot_sliding_window(audio_obj: Audio, seg: SlidingWindowFeature, out_path: Path) -> None:
    """stride / overlap の構造を波形 + gantt チャートで可視化する。"""
    sw = seg.sliding_window
    num_chunks = seg.data.shape[0]

    waveform = audio_obj.waveform[0].numpy()
    sr = audio_obj.sample_rate
    duration = len(waveform) / sr

    fig, (ax_wave, ax_chunks) = plt.subplots(
        2,
        1,
        figsize=(14, 2 + num_chunks * 0.18),
        gridspec_kw={"height_ratios": [1, 3]},
        sharex=True,
    )

    # ── 波形 ──
    step = max(1, len(waveform) // 8000)
    times = np.linspace(0, duration, len(waveform))
    ax_wave.plot(times[::step], waveform[::step], lw=0.4, color="steelblue")
    ax_wave.set_ylabel("振幅")
    ax_wave.set_title("音声波形")
    ax_wave.set_xlim(0, duration)

    # ── chunk gantt ──
    cmap = plt.cm.tab20
    overlap = sw.duration - sw.step
    for i in range(num_chunks):
        start = sw.start + i * sw.step
        color = cmap(i % 20)
        ax_chunks.barh(
            i,
            sw.duration,
            left=start,
            height=0.8,
            color=color,
            alpha=0.75,
            edgecolor="white",
            linewidth=0.4,
        )
        # overlap 部分をハイライト (前 chunk との重複)
        if i > 0:
            ax_chunks.barh(
                i,
                overlap,
                left=start,
                height=0.8,
                color="white",
                alpha=0.35,
                edgecolor="none",
            )

    ax_chunks.set_ylabel("chunk index")
    ax_chunks.set_xlabel("time (s)")
    ax_chunks.set_title(
        f"sliding window  stride={sw.step:.1f}s  window={sw.duration:.1f}s  "
        f"overlap={overlap:.1f}s ({overlap / sw.duration * 100:.0f}%)"
    )
    ax_chunks.set_ylim(-0.5, num_chunks - 0.5)
    ax_chunks.invert_yaxis()

    # stride / overlap 寸法の注釈 (最初の2チャンク間)
    y_ann = -0.3
    ax_chunks.annotate(
        "",
        xy=(sw.start + sw.step, y_ann),
        xytext=(sw.start, y_ann),
        arrowprops=dict(arrowstyle="<->", color="black", lw=1.2),
    )
    ax_chunks.text(
        sw.start + sw.step / 2,
        y_ann - 0.25,
        f"stride={sw.step:.1f}s",
        ha="center",
        va="top",
        fontsize=8,
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


def _plot_chunk_overlap(seg: SlidingWindowFeature, out_path: Path, n_chunks: int = 3) -> None:
    """最初のN chunkのlocal speaker活性化を絶対時刻軸で重ねて表示する。

    オーバーラップ領域でchunk間のlocal_spkがどう対応するか確認できる。
    """
    d = seg.data  # (num_chunks, num_frames, num_local_spk)
    sw = seg.sliding_window
    n = min(n_chunks, d.shape[0])
    num_frames = d.shape[1]
    num_local_spk = d.shape[2]

    chunk_colors = ["tab:blue", "tab:orange", "tab:green", "tab:red"]
    spk_styles = ["-", "--", ":"]
    fig, axes = plt.subplots(n, 1, figsize=(14, 3 * n), sharex=True)
    if n == 1:
        axes = [axes]

    # 全chunkの時間範囲
    t_start_global = sw.start
    t_end_global = sw.start + (n - 1) * sw.step + sw.duration

    for i in range(n):
        ax = axes[i]
        chunk_start = sw.start + i * sw.step
        chunk_end = chunk_start + sw.duration
        frame_times = chunk_start + np.linspace(0, sw.duration, num_frames, endpoint=False)

        # オーバーラップ領域をシェード
        if i > 0:
            prev_end = sw.start + (i - 1) * sw.step + sw.duration
            ax.axvspan(
                chunk_start, prev_end, color="yellow", alpha=0.25, label="前chunkとのoverlap"
            )
        if i < n - 1:
            next_start = sw.start + (i + 1) * sw.step
            ax.axvspan(next_start, chunk_end, color="cyan", alpha=0.2, label="次chunkとのoverlap")

        # chunk範囲の枠線
        ax.axvline(
            chunk_start, color=chunk_colors[i % len(chunk_colors)], lw=1.5, ls="-", alpha=0.6
        )
        ax.axvline(chunk_end, color=chunk_colors[i % len(chunk_colors)], lw=1.5, ls="-", alpha=0.6)

        for s in range(num_local_spk):
            ax.plot(
                frame_times,
                d[i, :, s],
                lw=1.2,
                ls=spk_styles[s % len(spk_styles)],
                color=chunk_colors[i % len(chunk_colors)],
                alpha=0.5 + 0.25 * s,
                label=f"local_spk[{s}]",
            )

        ax.set_ylabel("activation")
        ax.set_ylim(-0.05, 1.1)
        ax.set_title(f"chunk[{i}]  ({chunk_start:.1f}s ~ {chunk_end:.1f}s)")
        ax.legend(loc="upper right", fontsize=8)
        ax.set_xlim(t_start_global, t_end_global)

    axes[-1].set_xlabel("time (s)")
    fig.suptitle(
        f"最初の {n} chunk のlocal speaker活性化 (絶対時刻軸)\n"
        f"stride={sw.step:.1f}s  window={sw.duration:.1f}s  "
        f"overlap={sw.duration - sw.step:.1f}s"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


def _plot_count_aggregation(
    seg: SlidingWindowFeature,
    count: SlidingWindowFeature,
    out_path: Path,
    n_chunks: int = 3,
) -> None:
    """speaker_counting の集計過程を可視化する。

    上段: 各chunkの per-frame 同時発話数 (絶対時刻軸)
    中段: オーバーラップ領域での平均化の様子
    下段: 最終的な count (rounded)
    """
    d = seg.data  # (num_chunks, num_frames, num_local_spk)
    sw = seg.sliding_window
    n = min(n_chunks, d.shape[0])
    num_frames = d.shape[1]

    chunk_colors = ["tab:blue", "tab:orange", "tab:green", "tab:red"]

    fig, (ax_per, ax_sum, ax_final) = plt.subplots(3, 1, figsize=(14, 8), sharex=True)

    t_end = sw.start + (n - 1) * sw.step + sw.duration

    # ── 上段: 各chunkのper-frame同時発話数 ──
    for i in range(n):
        chunk_start = sw.start + i * sw.step
        frame_times = chunk_start + np.linspace(0, sw.duration, num_frames, endpoint=False)
        per_frame_count = (d[i] > 0).sum(axis=-1)  # (num_frames,)
        ax_per.step(
            frame_times,
            per_frame_count + i * 0.05,  # 少しずらして重なりを見やすく
            where="post",
            lw=1.5,
            color=chunk_colors[i % len(chunk_colors)],
            label=f"chunk[{i}] ({chunk_start:.0f}~{chunk_start + sw.duration:.0f}s)",
        )
    ax_per.set_ylabel("同時発話数\n(各chunk独立)")
    ax_per.set_ylim(-0.2, 3.5)
    ax_per.set_yticks([0, 1, 2, 3])
    ax_per.legend(fontsize=8, loc="upper right")
    ax_per.set_title(f"① 各chunk単独のper-frame同時発話数 (最初の{n} chunk)")

    # ── 中段: オーバーラップ領域での重み付け平均の様子 ──
    # 各時刻で何chunkが重なっているかを計算
    resolution = sw.step / num_frames  # ≈ frame step in seconds
    t_axis = np.arange(sw.start, t_end, resolution / 2)
    overlap_count = np.zeros_like(t_axis)
    weighted_sum = np.zeros_like(t_axis)

    for i in range(n):
        chunk_start = sw.start + i * sw.step
        frame_times = chunk_start + np.linspace(0, sw.duration, num_frames, endpoint=False)
        per_frame = (d[i] > 0).sum(axis=-1).astype(float)
        # 補間して t_axis に乗せる
        vals = np.interp(t_axis, frame_times, per_frame, left=np.nan, right=np.nan)
        in_range = (t_axis >= chunk_start) & (t_axis < chunk_start + sw.duration)
        overlap_count += in_range.astype(float)
        weighted_sum = np.where(in_range, weighted_sum + np.nan_to_num(vals), weighted_sum)

    averaged = np.where(overlap_count > 0, weighted_sum / overlap_count, np.nan)

    # オーバーラップ数をシェードで表示
    for i in range(n):
        chunk_start = sw.start + i * sw.step
        ax_sum.axvspan(
            chunk_start,
            chunk_start + sw.duration,
            alpha=0.08,
            color=chunk_colors[i % len(chunk_colors)],
        )

    ax_sum.plot(t_axis, averaged, lw=1.5, color="black", label="overlap平均")
    ax_sum.plot(
        t_axis, overlap_count * 0.3, lw=1, ls="--", color="gray", label="重複chunk数×0.3 (参考)"
    )
    ax_sum.set_ylabel("平均 同時発話数")
    ax_sum.set_ylim(-0.2, 3.5)
    ax_sum.set_yticks([0, 1, 2, 3])
    ax_sum.legend(fontsize=8, loc="upper right")
    ax_sum.set_title("② オーバーラップ領域での平均化 (aggregate)")

    # ── 下段: 実際のcount出力 (全音声) ──
    count_d = count.data.squeeze()
    count_sw = count.sliding_window
    count_times = count_sw.start + np.arange(len(count_d)) * count_sw.step
    # 最初のn chunkの範囲だけ表示
    mask = count_times <= t_end
    ax_final.step(
        count_times[mask],
        count_d[mask],
        where="post",
        lw=2,
        color="crimson",
        label="speaker_count (rounded)",
    )
    ax_final.set_ylabel("count (整数)")
    ax_final.set_ylim(-0.2, 3.5)
    ax_final.set_yticks([0, 1, 2, 3])
    ax_final.set_xlabel("time (s)")
    ax_final.legend(fontsize=8, loc="upper right")
    ax_final.set_title("③ 最終 speaker_count 出力 (np.rint → uint8)")

    ax_final.set_xlim(sw.start, t_end)
    fig.suptitle(
        f"speaker_counting の集計過程 (最初の{n} chunk)\n"
        f"※ count は『同時発話数』。グローバル話者数はclusteringが決める"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


def _plot_embedding_pca(
    emb: np.ndarray,
    hard_clusters: np.ndarray,
    out_path: Path,
) -> None:
    """embedding を PCA で2次元に落とし、話者・chunk・local_spk を色/形で表示する。

    色  = グローバル話者 (clustering結果)
    形  = local_spk index (0=○, 1=□, 2=△)
    番号 = chunk index
    """
    from sklearn.decomposition import PCA

    num_chunks, num_local_spk, dim = emb.shape
    flat_emb = emb.reshape(-1, dim)  # (chunks*local_spk, 256)
    flat_clusters = hard_clusters.flatten()  # (chunks*local_spk,)

    # active な点だけ使う (-2=inactive, NaN=inactive)
    active_mask = (flat_clusters >= 0) & (~np.isnan(flat_emb).any(axis=-1))
    active_emb = flat_emb[active_mask]
    active_clusters = flat_clusters[active_mask]
    active_idx = np.where(active_mask)[0]  # 元のインデックス

    if len(active_emb) == 0:
        print("  active embedding が0件のためスキップ")
        return

    # PCA
    pca = PCA(n_components=2)
    xy = pca.fit_transform(active_emb)
    var = pca.explained_variance_ratio_

    # 話者ラベル → 色
    n_speakers = int(active_clusters.max()) + 1
    spk_colors = plt.cm.tab10(np.linspace(0, 1, max(n_speakers, 2)))
    marker_list = ["o", "s", "^"]

    fig, ax = plt.subplots(figsize=(10, 8))

    for spk in range(n_speakers):
        for s in range(num_local_spk):
            sel = (active_clusters == spk) & (active_idx % num_local_spk == s)
            if not sel.any():
                continue
            ax.scatter(
                xy[sel, 0],
                xy[sel, 1],
                c=[spk_colors[spk]],
                marker=marker_list[s % len(marker_list)],
                s=80,
                alpha=0.8,
                edgecolors="white",
                linewidths=0.5,
                label=f"SPEAKER_{spk:02d} / local_spk[{s}]" if sel.sum() > 0 else None,
            )

    # chunk番号ラベル
    for i, (x, y) in enumerate(xy):
        chunk_idx = active_idx[i] // num_local_spk
        ax.annotate(
            str(chunk_idx), (x, y), fontsize=6, alpha=0.6, xytext=(3, 3), textcoords="offset points"
        )

    ax.set_xlabel(f"PC1 ({var[0] * 100:.1f}%)")
    ax.set_ylabel(f"PC2 ({var[1] * 100:.1f}%)")
    ax.set_title(
        f"Embedding PCA (active {len(active_emb)}/{len(flat_emb)} 点)\n"
        f"色=グローバル話者  形=local_spk(○□△)  数字=chunk番号"
    )
    # 凡例を話者単位にまとめる
    handles, labels = ax.get_legend_handles_labels()
    seen = {}
    for h, label in zip(handles, labels, strict=False):
        key = label.split(" / ")[0]
        if key not in seen:
            seen[key] = h
    ax.legend(seen.values(), seen.keys(), fontsize=9, loc="best")

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


def _plot_embedding_detail(
    pipeline: object,
    audio_obj: Audio,
    seg: SlidingWindowFeature,
    emb: np.ndarray,
    out_path: Path,
    per_chunk: bool = False,
    chunk_idx: int | None = None,
) -> None:
    """embedding 計算の中間値を可視化する (1 chunk)。

    per_chunk=True : forward_features (frame特徴heatmap) + 話者マスク + pooling後ベクトル
    per_chunk=False: 話者マスクで切り出した音声区間 + pooling後ベクトル
    """
    import torch

    sw = seg.sliding_window
    num_chunks, num_frames, num_local_spk = seg.data.shape

    # 2話者以上が活性なchunkを自動選択
    if chunk_idx is None:
        n_active_spk = (seg.data > 0.5).any(axis=1).sum(axis=1)  # (num_chunks,)
        chunk_idx = int(np.argmax(n_active_spk))
    n_active = int((seg.data[chunk_idx] > 0.5).any(axis=0).sum())
    print(f"  対象 chunk: [{chunk_idx}]  (active local_spk 数: {n_active})")

    chunk_start = sw.start + chunk_idx * sw.step
    chunk_end = chunk_start + sw.duration
    frame_times = chunk_start + np.linspace(0, sw.duration, num_frames, endpoint=False)

    # chunk waveform を取得
    sr = audio_obj.sample_rate
    s_idx = max(0, int(round(chunk_start * sr)))
    e_idx = min(audio_obj.waveform.shape[1], int(round(chunk_end * sr)))
    chunk_wav_np = audio_obj.waveform[0, s_idx:e_idx].numpy()
    wav_times = np.linspace(chunk_start, chunk_end, len(chunk_wav_np))

    masks = seg.data[chunk_idx]  # (num_frames, num_local_spk)

    spk_colors = ["tab:blue", "tab:orange", "tab:green"]

    if per_chunk:
        # ── per_chunk=True: forward_features → frame特徴 → masked pooling ──
        embedder = pipeline.embedder  # type: ignore[attr-defined]
        model = embedder.model

        # chunk waveformをtensorに
        chunk_wav_t = audio_obj.waveform[:, s_idx:e_idx].unsqueeze(0).to(embedder.device)
        expected = int(round(sw.duration * sr))
        if chunk_wav_t.shape[-1] < expected:
            chunk_wav_t = torch.nn.functional.pad(
                chunk_wav_t, (0, expected - chunk_wav_t.shape[-1])
            )

        with torch.inference_mode():
            features = model.forward_features(chunk_wav_t)  # type: ignore[operator]  # (1, C, T)
        feat_np = features[0].cpu().numpy()  # (C, T)
        C, T = feat_np.shape

        # masks を T フレームにリサンプル
        masks_T = np.array(
            [
                np.interp(np.linspace(0, 1, T), np.linspace(0, 1, num_frames), masks[:, s])
                for s in range(num_local_spk)
            ]
        )  # (num_local_spk, T)

        fig = plt.figure(figsize=(14, 10))
        gs = fig.add_gridspec(4, num_local_spk + 1, hspace=0.45, wspace=0.3)

        # 行0: 波形
        ax_wav = fig.add_subplot(gs[0, :])
        ax_wav.plot(wav_times, chunk_wav_np, lw=0.5, color="gray")
        ax_wav.set_title(f"chunk[{chunk_idx}] 波形 ({chunk_start:.1f}s ~ {chunk_end:.1f}s)")
        ax_wav.set_ylabel("振幅")

        # 行1: frame特徴 heatmap (全チャンネル)
        ax_feat = fig.add_subplot(gs[1, :])
        im = ax_feat.imshow(
            feat_np[:64],
            aspect="auto",
            origin="lower",
            extent=[chunk_start, chunk_end, 0, min(64, C)],
            cmap="viridis",
        )
        ax_feat.set_title(f"forward_features() — frame特徴 (shape: C={C}, T={T}, 上位64ch表示)")
        ax_feat.set_ylabel("channel")
        fig.colorbar(im, ax=ax_feat, shrink=0.6)

        # 行2: 話者マスク
        ax_mask = fig.add_subplot(gs[2, :])
        t_axis = np.linspace(chunk_start, chunk_end, T)
        for s in range(num_local_spk):
            ax_mask.plot(t_axis, masks_T[s], lw=1.2, color=spk_colors[s], label=f"local_spk[{s}]")
        ax_mask.set_title("segmentation マスク (話者ごとの重み)")
        ax_mask.set_ylabel("activation")
        ax_mask.set_ylim(-0.05, 1.1)
        ax_mask.legend(fontsize=9)

        # 行3: 話者ごとの masked pool (line) + 最終embedding (line)
        for s in range(num_local_spk):
            ax = fig.add_subplot(gs[3, s])
            w = masks_T[s]  # (T,)
            w_sum = w.sum()
            if w_sum > 1e-6:
                pooled = (feat_np * w[np.newaxis, :]).sum(axis=1) / w_sum  # (C,)
            else:
                pooled = np.zeros(C)
            ax.plot(np.arange(min(64, C)), pooled[:64], lw=0.8, color=spk_colors[s])
            ax.axhline(0, color="gray", lw=0.5, ls="--")
            ax.set_title(f"local_spk[{s}]\nweighted pool (上位64ch)")
            ax.set_xlabel("channel")
            ax.set_ylabel("値")

        ax_emb = fig.add_subplot(gs[3, num_local_spk])
        e0 = emb[chunk_idx, 0, :] if emb.ndim == 3 else np.full(256, np.nan)
        e1 = emb[chunk_idx, 1, :] if emb.ndim == 3 and num_local_spk > 1 else np.full(256, np.nan)
        if not np.isnan(e0).all():
            ax_emb.plot(e0[:64], lw=0.8, color=spk_colors[0], label="spk[0]")
        if not np.isnan(e1).all():
            ax_emb.plot(e1[:64], lw=0.8, color=spk_colors[1], label="spk[1]")
        ax_emb.axhline(0, color="gray", lw=0.5, ls="--")
        ax_emb.set_title("最終 embedding\n(256次元、上位64次元)")
        ax_emb.set_xlabel("次元")
        ax_emb.legend(fontsize=8)

        fig.suptitle(f"Embedding 計算過程 (per_chunk=True)  chunk[{chunk_idx}]", fontsize=13)

    else:
        # ── per_chunk=False: 話者マスクで切り出した音声 + embedding ──
        fig, axes = plt.subplots(
            num_local_spk + 1, 1, figsize=(14, 3 * (num_local_spk + 1)), sharex=False
        )

        for s in range(num_local_spk):
            ax = axes[s]
            # マスクを波形時刻にリサンプル
            mask_wav = np.interp(
                np.linspace(0, 1, len(chunk_wav_np)),
                np.linspace(0, 1, num_frames),
                masks[:, s],
            )
            ax.plot(wav_times, chunk_wav_np, lw=0.4, color="lightgray")
            # 活性区間をハイライト
            active = mask_wav > 0.5
            ax.fill_between(
                wav_times,
                chunk_wav_np,
                where=active,
                color=spk_colors[s],
                alpha=0.6,
                label="発話区間",
            )
            ax.plot(
                frame_times,
                masks[:, s] * np.abs(chunk_wav_np).max(),
                lw=1,
                color=spk_colors[s],
                ls="--",
                label="activation (スケール済み)",
            )
            ax.set_title(f"local_spk[{s}] — 切り出し音声区間 (この区間をエンコーダに入力)")
            ax.set_ylabel("振幅")
            ax.legend(fontsize=8, loc="upper right")

        ax_emb = axes[-1]
        for s in range(num_local_spk):
            e = emb[chunk_idx, s, :] if emb.ndim == 3 else np.full(256, np.nan)
            if not np.isnan(e).all():
                ax_emb.plot(e, lw=0.8, color=spk_colors[s], label=f"spk[{s}] embedding")
        ax_emb.set_title("最終 embedding (256次元)")
        ax_emb.set_xlabel("次元")
        ax_emb.legend(fontsize=9)

        fig.suptitle(f"Embedding 計算過程 (per_chunk=False)  chunk[{chunk_idx}]", fontsize=13)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


def _plot_clustering_dendrogram(
    emb: np.ndarray,
    hard_clusters: np.ndarray,
    out_path: Path,
) -> None:
    """AHC のデンドログラムを描画する。

    縦軸 = cosine距離 (小さいほど似ている)
    横軸 = 各 embedding (ラベル: c{chunk}s{local_spk})
    赤破線 = threshold (ここで切ると今回のクラスタ数になる)
    葉の色 = global 話者 (clustering 結果)
    """
    from scipy.cluster.hierarchy import dendrogram

    from voxmap.clustering.ahc import AHC

    num_chunks, num_local_spk, dim = emb.shape
    flat_emb = emb.reshape(-1, dim)
    flat_clusters = hard_clusters.flatten()

    active_mask = (flat_clusters >= 0) & (~np.isnan(flat_emb).any(axis=-1))
    active_emb = flat_emb[active_mask]
    active_clusters = flat_clusters[active_mask]
    active_idx = np.where(active_mask)[0]

    if len(active_emb) < 2:
        print("  active embedding が2件未満のためスキップ")
        return

    labels = [f"c{idx // num_local_spk}s{idx % num_local_spk}" for idx in active_idx]

    # linkage 計算 (pipeline と同じ設定)
    threshold = 0.7045654963945799
    Z = AHC.compute_linkage(active_emb, method="centroid", metric="cosine")

    # 葉の色を global 話者で設定
    n_speakers = int(active_clusters.max()) + 1
    spk_cmap = plt.cm.tab10
    leaf_colors = {
        label: spk_cmap(active_clusters[i] / max(n_speakers, 2)) for i, label in enumerate(labels)
    }

    n = len(active_emb)
    fig_w = max(14, n * 0.35)
    fig, ax = plt.subplots(figsize=(fig_w, 6))

    dendrogram(
        Z,
        labels=labels,
        ax=ax,
        color_threshold=0,
        above_threshold_color="gray",
        leaf_rotation=90,
        leaf_font_size=max(5, 9 - n // 15),
    )

    # 葉ラベルの色を global 話者で上書き
    for text in ax.get_xticklabels():
        name = text.get_text()
        if name in leaf_colors:
            text.set_color(leaf_colors[name])

    # threshold ライン
    ax.axhline(threshold, color="crimson", lw=1.5, ls="--", label=f"threshold = {threshold:.4f}")

    # 距離軸の意味注釈
    ax.set_ylabel("cosine 距離 (小 = 似ている)")
    ax.set_xlabel("embedding  (c{chunk}s{local_spk}、色 = global 話者)")
    ax.set_title(
        f"AHC デンドログラム  (active {n} embeddings, {n_speakers} speakers)\n"
        f"赤破線より上でマージ → 別クラスタ / 赤破線より下でマージ → 同一クラスタ"
    )
    ax.legend(fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


def _plot_cosine_similarity(
    emb: np.ndarray,
    hard_clusters: np.ndarray,
    out_path: Path,
) -> None:
    """active embedding 間のコサイン類似度行列をヒートマップで表示する。"""
    from scipy.spatial.distance import cdist

    num_chunks, num_local_spk, dim = emb.shape
    flat_emb = emb.reshape(-1, dim)
    flat_clusters = hard_clusters.flatten()

    active_mask = (flat_clusters >= 0) & (~np.isnan(flat_emb).any(axis=-1))
    active_emb = flat_emb[active_mask]
    active_clusters = flat_clusters[active_mask]
    active_idx = np.where(active_mask)[0]

    if len(active_emb) == 0:
        print("  active embedding が0件のためスキップ")
        return

    # コサイン類似度 = 1 - cosine距離
    cos_dist = cdist(active_emb, active_emb, metric="cosine")
    cos_sim = 1.0 - cos_dist

    # ラベル: c{chunk}s{local_spk}
    labels = [f"c{idx // num_local_spk}s{idx % num_local_spk}" for idx in active_idx]

    # global 話者ごとの色
    n_speakers = int(active_clusters.max()) + 1
    spk_cmap = plt.cm.tab10
    spk_colors = [spk_cmap(s / max(n_speakers, 2)) for s in active_clusters]

    n = len(active_emb)
    fig_size = max(8, n * 0.22)
    fig, ax = plt.subplots(figsize=(fig_size + 1.5, fig_size))

    im = ax.imshow(cos_sim, vmin=-1, vmax=1, cmap="RdYlGn", aspect="auto")
    fig.colorbar(im, ax=ax, label="cosine similarity", shrink=0.6)

    ax.set_xticks(np.arange(n))
    ax.set_yticks(np.arange(n))
    ax.set_xticklabels(labels, rotation=90, fontsize=max(5, 8 - n // 20))
    ax.set_yticklabels(labels, fontsize=max(5, 8 - n // 20))

    # 行・列の話者カラーバー (tick色で表現)
    for tick, color in zip(ax.get_xticklabels(), spk_colors, strict=False):
        tick.set_color(color)
    for tick, color in zip(ax.get_yticklabels(), spk_colors, strict=False):
        tick.set_color(color)

    # threshold ライン (threshold を超えたら別クラスタ → 類似度 = 1 - threshold)
    threshold_sim = 1.0 - 0.7045654963945799
    ax.contour(cos_sim, levels=[threshold_sim], colors="black", linewidths=0.8, linestyles="--")

    # 話者ブロックの境界線
    speaker_change = np.where(np.diff(active_clusters))[0] + 1
    for pos in speaker_change:
        ax.axhline(pos - 0.5, color="navy", lw=1.5)
        ax.axvline(pos - 0.5, color="navy", lw=1.5)

    ax.set_title(
        f"Cosine Similarity 行列  (active {n} embeddings)\n"
        f"ラベル色 = global話者  破線 = threshold (sim={threshold_sim:.3f})\n"
        f"青縦横線 = 話者境界 (clusteringで分けた結果)"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


def _plot_segmentation(seg: SlidingWindowFeature, out_path: Path) -> None:
    d = seg.data  # (chunks, frames, 3)
    num_chunks, num_frames, num_local_spk = d.shape
    sw = seg.sliding_window

    fig, axes = plt.subplots(
        num_local_spk + 1, 1, figsize=(14, 3 * (num_local_spk + 1)), sharex=True
    )

    chunk_times = sw.start + np.arange(num_chunks) * sw.step

    # 各 local speaker の活性化を heatmap で表示
    for s in range(num_local_spk):
        ax = axes[s]
        im = ax.imshow(
            d[:, :, s].T,
            aspect="auto",
            origin="lower",
            extent=[chunk_times[0], chunk_times[-1] + sw.duration, 0, num_frames],
            vmin=0,
            vmax=1,
            cmap="Reds",
        )
        ax.set_ylabel(f"local_spk[{s}]\n(frame)")
        ax.set_title(f"segmentation activation — local speaker {s}")
        fig.colorbar(im, ax=ax, shrink=0.8)

    # 同時発話数 (frames を chunk-avg して折れ線)
    ax = axes[-1]
    simultaneous = (d > 0).sum(axis=2)  # (chunks, frames)
    per_chunk_mean = simultaneous.mean(axis=1)  # (chunks,)
    ax.plot(chunk_times, per_chunk_mean, lw=1)
    ax.set_ylabel("avg active\nspeakers/frame")
    ax.set_xlabel("time (s)")
    ax.set_title("平均同時発話話者数 (chunk ごと)")
    ax.set_ylim(0, num_local_spk + 0.2)

    fig.suptitle("Segmentation ステージ出力")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


def _plot_speaker_count(count: SlidingWindowFeature, out_path: Path) -> None:
    d = count.data.squeeze()  # (num_frames,)
    sw = count.sliding_window
    times = sw.start + np.arange(len(d)) * sw.step

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4))

    ax1.step(times, d, where="mid", lw=0.8)
    ax1.set_xlabel("time (s)")
    ax1.set_ylabel("instantaneous speaker count")
    ax1.set_title("Speaker count (frame-level)")
    ax1.set_ylim(-0.2, d.max() + 0.5)

    vals, cnts = np.unique(d.astype(int), return_counts=True)
    ax2.bar(vals, cnts / cnts.sum() * 100)
    ax2.set_xlabel("同時発話話者数")
    ax2.set_ylabel("割合 (%)")
    ax2.set_title("Speaker count 分布")
    ax2.set_xticks(vals)

    fig.suptitle("Speaker Counting ステージ出力")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  → saved: {out_path}")


@app.command()
def main(
    audio: Path = typer.Option(  # noqa: B008
        Path("data/raw/ami/audio/TS3003c.Mix-Headset.wav"),
        help="解析する音声ファイル",
    ),
    seconds: float = typer.Option(30.0, help="先頭何秒を使うか (0=全体)"),  # noqa: B008
    stride: float = typer.Option(1.0, help="segmentation_step (1.0=デフォルト, 3.0=実験値)"),  # noqa: B008
    device_str: str = typer.Option("cpu", help="cpu / cuda / mps"),  # noqa: B008
    out_dir: Path = typer.Option(Path("/tmp/pipeline_inspect"), help="図の出力先"),  # noqa: B008
    per_chunk: bool = typer.Option(False, help="per-chunk embedding モードを使う (CAM++のみ)"),  # noqa: B008
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(device_str)

    # ── 音声ロード ──────────────────────────────────────────────
    _section("音声ロード")
    waveform, sr = torchaudio.load(str(audio))
    if seconds > 0:
        waveform = waveform[:, : int(seconds * sr)]
    print(f"  ファイル : {audio.name}")
    print(f"  shape   : {waveform.shape}  (sr={sr}Hz)")
    print(f"  長さ    : {waveform.shape[1] / sr:.1f}s")
    audio_obj = Audio(waveform=waveform, sample_rate=sr)

    # ── pipeline ロード ─────────────────────────────────────────
    _section("Pipeline ロード")
    print(f"  segmentation_step={stride}  device={device_str}")
    pipeline = load_diarization31_pipeline(
        segmentation_model="pyannote/segmentation-3.0",
        embedding_model="Wespeaker/wespeaker-voxceleb-campplus",
        threshold=0.7045654963945799,
        method="centroid",
        min_cluster_size=12,
        embedding_batch_size=32,
        segmentation_batch_size=32,
        embedding_exclude_overlap=True,
        segmentation_step=stride,
        embedding_per_chunk=per_chunk,
        device=device,
    )
    print("  ロード完了")

    # ── hook で中間値を補足 ─────────────────────────────────────
    captured: dict[str, object] = {}

    def hook(name: str, value: object, **kwargs: object) -> None:
        # progress hook は value=None なのでスキップ
        if value is not None:
            captured[name] = value

    # ── 実行 ────────────────────────────────────────────────────
    _section("Pipeline 実行")
    result = pipeline(audio_obj, hook=hook)
    print(f"  検出話者数: {len(result.labels())}")
    print(f"  labels   : {result.labels()}")

    # ── ステージ1: segmentation ─────────────────────────────────
    _section("ステージ1: Segmentation 出力")
    seg: SlidingWindowFeature = captured["segmentation"]

    # ── sliding window 可視化 ────────────────────────────────────
    _section("Sliding Window 構造")
    _plot_sliding_window(audio_obj, seg, out_dir / "00_sliding_window.png")

    # ── chunk間 local speaker 対応 ───────────────────────────────
    _section("Chunk間 Local Speaker 活性化 (最初の3 chunk)")
    _plot_chunk_overlap(seg, out_dir / "01b_chunk_overlap.png", n_chunks=3)
    print(f"""
  SlidingWindowFeature とは?
    各 chunk (10s ウィンドウ) で PyanNet が出力した、
    frame ごとの local-speaker 活性化スコア (0 or 1 の multilabel)。
    chunk_window.step = stride (={stride}s) で次の chunk へ進む。
""")
    _print_swf("segmentation", seg)
    _plot_segmentation(seg, out_dir / "01_segmentation.png")

    # ── ステージ2: speaker_counting ─────────────────────────────
    _section("ステージ2: Speaker Counting 出力")
    count: SlidingWindowFeature = captured["speaker_counting"]

    # ── speaker count 集計過程 ───────────────────────────────────
    _section("Speaker Count 集計過程 (最初の3 chunk)")
    _plot_count_aggregation(seg, count, out_dir / "02b_count_aggregation.png", n_chunks=3)
    print("""
  SlidingWindowFeature とは?
    各 frame における「同時発話している話者の推定数」。
    segmentation の local-speaker 活性化を全 chunk にわたって統合し、
    pyannote の speaker_count() が frame-level に折りたたんだもの。
    clustering → reconstruct が「何人分の global speaker 列を作るか」を
    ここで決める。
""")
    _print_swf("speaker_counting", count)
    _plot_speaker_count(count, out_dir / "02_speaker_count.png")

    # ── ステージ3: embeddings ────────────────────────────────────
    _section("ステージ3: Embedding 出力 (概要)")
    emb: np.ndarray = captured["embeddings"]
    print("""
  ndarray とは?
    各 (chunk, local_speaker) ペアの話者埋め込みベクトル (256次元)。
    inactive な (chunk, speaker) ペアは NaN。
    AHC は NaN を除いた行だけを cosine 距離でクラスタリングする。
""")
    # embeddings は (num_chunks, 3, 256) の 3D array のこともある
    if emb.ndim == 3:
        num_chunks, num_local, dim = emb.shape
        print(
            f"  shape    : {emb.shape}  → (chunks={num_chunks}, local_spk={num_local}, dim={dim})"
        )
        flat = emb.reshape(-1, dim)
        _print_embeddings(flat)
        print()
        for s in range(num_local):
            col = emb[:, s, :]
            nan_cnt = np.isnan(col).any(axis=-1).sum()
            print(
                f"  local_spk[{s}]: active chunks = {num_chunks - nan_cnt}/{num_chunks}  "
                f"(NaN={nan_cnt})"
            )
    else:
        _print_embeddings(emb)

    # ── embedding PCA ────────────────────────────────────────────
    _section("Embedding PCA (話者クラスタ可視化)")
    hard_clusters: np.ndarray = captured["hard_clusters"]
    _plot_embedding_pca(emb, hard_clusters, out_dir / "03_embedding_pca.png")

    # ── クラスタリング デンドログラム ────────────────────────────
    _section("AHC デンドログラム")
    _plot_clustering_dendrogram(emb, hard_clusters, out_dir / "04_dendrogram.png")

    # ── コサイン類似度行列 ───────────────────────────────────────
    _section("Cosine Similarity 行列")
    _plot_cosine_similarity(emb, hard_clusters, out_dir / "03c_cosine_similarity.png")

    # ── embedding 計算過程 ───────────────────────────────────────
    _section("Embedding 計算過程 (1 chunk 詳細)")
    _plot_embedding_detail(
        pipeline,
        audio_obj,
        seg,
        emb,
        out_dir / "03b_embedding_detail.png",
        per_chunk=per_chunk,
    )

    # ── まとめ ──────────────────────────────────────────────────
    _section("データフロー まとめ")
    seg_d = seg.data
    count_d = count.data.squeeze()
    num_chunks = seg_d.shape[0]
    num_frames_seg = seg_d.shape[1]
    num_frames_count = len(count_d)
    sw = seg.sliding_window
    seg_end = sw.start + (num_chunks - 1) * sw.step + sw.duration
    emb_flat = emb.reshape(-1, emb.shape[-1])
    emb_active = (~np.isnan(emb_flat).any(axis=-1)).sum()
    print(f"""
  音声長さ          : {audio_obj.waveform.shape[1] / audio_obj.sample_rate:.1f}s
  stride            : {stride}s

  segmentation出力
    chunk 数         : {num_chunks}
    frames/chunk     : {num_frames_seg}
    local speakers   : {seg_d.shape[2]}
    全体の time span : {sw.start:.1f}s 〜 {seg_end:.1f}s

  speaker_count 出力
    frame 数         : {num_frames_count}
    最大同時話者数   : {int(count_d.max())}
    frame step       : {count.sliding_window.step * 1000:.1f}ms

  embeddings 出力
    shape            : {emb.shape}
    active           : {emb_active} / {emb_flat.shape[0]}

  図の保存先: {out_dir}/
    00_sliding_window.png — stride / overlap 構造 (波形 + gantt)
    01_segmentation.png  — local speaker 活性化 heatmap
    02_speaker_count.png — frame-level 話者数
""")


if __name__ == "__main__":
    app()
