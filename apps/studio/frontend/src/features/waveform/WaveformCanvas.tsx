import { type PointerEvent as ReactPointerEvent, useEffect, useRef } from "react";
import { container } from "../../app/container.ts";
import { EDGE_PX, LANE_H, MAX_VISIBLE_LANES, STRIP_H, ZOOM_STEP } from "../../domain/constants.ts";
import { timeToX, type View, type Viewport, xToTime } from "../../domain/coords.ts";
import { laneAtY, laneCount, laneOf, lanesHeight } from "../../domain/lanes.ts";
import { createSegment, moveSegment, resizeEnd, resizeStart } from "../../domain/segment.ts";
import { overlapsRange } from "../../domain/speaker.ts";
import { markEdited } from "../../domain/status.ts";
import type { Segment } from "../../domain/types.ts";
import { useAudioStore } from "../../state/audioStore.ts";
import { BUCKET_SEC, useCoverageStore } from "../../state/coverageStore.ts";
import { useEditOpsStore } from "../../state/editOpsStore.ts";
import { newId, useEditorStore } from "../../state/editorStore.ts";
import { useModeStore } from "../../state/modeStore.ts";
import { usePlaybackStore } from "../../state/playbackStore.ts";
import { useViewStore } from "../../state/viewStore.ts";
import { useCanvasPalette } from "../../ui/theme/useTheme.ts";
import {
  drawCoverage,
  drawLanesBg,
  drawPlayhead,
  drawSegments,
  drawSelectionRect,
  drawWaveform,
} from "./render.ts";
import { detectPulses, hasActivePulses, pulseAlpha } from "./suspicionPulse.ts";

// Layout (案A):
//   ┌──────────────────────────┐  ← sticky strip canvas (STRIP_H px)
//   │ ruler + waveform         │    常に見える
//   ├──────────────────────────┤
//   │ lane 0  ███  ██          │  ← lanes canvas (LANE_H × n px)
//   │ lane 1     ████          │    話者が増えると縦に伸び下にスクロール
//   └──────────────────────────┘

type EditMode = "create" | "move" | "resize-start" | "resize-end" | "range" | "select-toggle";
type HoverMode = "resize-start" | "resize-end" | "move";

/** lanes canvas (top=0) でのヒット判定。 */
function hitSegment(
  segments: Segment[],
  view: View,
  x: number,
  y: number,
  speakers: string[],
  laneH: number,
): { seg: Segment; mode: HoverMode } | null {
  const n = laneCount(speakers);
  const lane = laneAtY(y, laneH, 0, n);
  const inLane = (s: Segment) => laneOf(s.speaker, speakers) === lane;

  // 1) まずカーソルが含まれるセグメントを半開区間 [x0, x1) で一意に決める。
  //    隣接する 2 区間が境界を共有していても (split 直後など)、境界はカーソルの
  //    「ある側」に属するため、左をクリックすれば左が選ばれる (右の resize ハンドルに
  //    奪われない)。エッジ判定を先にすると後勝ち (配列後方=右) で右が選ばれてしまう。
  let target: { seg: Segment; x0: number; x1: number } | null = null;
  for (let i = segments.length - 1; i >= 0; i--) {
    const s = segments[i];
    if (!s || !inLane(s)) continue;
    const x0 = timeToX(s.start, view);
    const x1 = timeToX(s.end, view);
    if (x >= x0 && x < x1) {
      target = { seg: s, x0, x1 };
      break;
    }
  }

  // 2) どの body にも含まれない (隙間 / 端の外側 EDGE_PX) 場合は、最寄りの端で拾う。
  //    端を外側から掴んで resize するケース。
  if (!target) {
    for (let i = segments.length - 1; i >= 0; i--) {
      const s = segments[i];
      if (!s || !inLane(s)) continue;
      const x0 = timeToX(s.start, view);
      const x1 = timeToX(s.end, view);
      if (x >= x0 - EDGE_PX && x <= x1 + EDGE_PX) {
        target = { seg: s, x0, x1 };
        break;
      }
    }
  }
  if (!target) return null;

  // 3) mode は「決まったセグメント自身の端」との距離で決める。端に近ければ resize、
  //    そうでなければ move。境界判定 (どの区間か) は 1〜2 で済んでいる。
  const { seg, x0, x1 } = target;
  if (Math.abs(x - x0) <= EDGE_PX) return { seg, mode: "resize-start" };
  if (Math.abs(x - x1) <= EDGE_PX) return { seg, mode: "resize-end" };
  return { seg, mode: "move" };
}

function speakerAtY(y: number, speakers: string[], laneH: number): string | null {
  if (speakers.length === 0) return null;
  return speakers[laneAtY(y, laneH, 0, laneCount(speakers))] ?? null;
}

interface DragState {
  startX: number;
  startY: number;
  startTime: number;
  mode: EditMode;
  origSeg: Segment | null;
  createSpeaker: string | null;
  additive: boolean;
  moved: boolean;
  began: boolean;
}

export function WaveformCanvas() {
  const wrapperRef = useRef<HTMLDivElement>(null); // 全体ラッパー (幅計測)
  const stripRef = useRef<HTMLCanvasElement>(null); // 波形 sticky canvas
  const lanesRef = useRef<HTMLCanvasElement>(null); // 区間 scrollable canvas
  const widthRef = useRef(0);
  const dragRef = useRef<DragState | null>(null);
  const previewRef = useRef<{ x0: number; x1: number; createSpeaker?: string | null } | null>(null);
  const requestStripRef = useRef<() => void>(() => {});
  const requestLanesRef = useRef<() => void>(() => {});

  const audio = useAudioStore((s) => s.audio);
  const palette = useCanvasPalette();
  const laneN = useEditorStore((s) => laneCount(s.speakers));
  const lanesH = lanesHeight(laneN);

  const viewport = (): Viewport => ({
    widthPx: widthRef.current,
    duration: audio?.duration ?? 0,
  });

  // 幅変化 / 話者数変化でバッキングサイズを更新。
  useEffect(() => {
    const wrapper = wrapperRef.current;
    const strip = stripRef.current;
    const lanes = lanesRef.current;
    if (!wrapper || !strip || !lanes) return;

    const resize = () => {
      const width = wrapper.clientWidth;
      widthRef.current = width;
      const dpr = window.devicePixelRatio || 1;
      strip.width = Math.round(width * dpr);
      strip.height = Math.round(STRIP_H * dpr);
      lanes.width = Math.round(width * dpr);
      lanes.height = Math.round(lanesH * dpr);
      // centerOn 等が使えるよう最新のビューポートを記録。
      useViewStore.getState().setViewport({
        widthPx: width,
        duration: useAudioStore.getState().audio?.duration ?? 0,
      });
      requestStripRef.current();
      requestLanesRef.current();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrapper);
    return () => ro.disconnect();
  }, [lanesH]);

  // 音声ロード時にフィット。
  useEffect(() => {
    if (audio) {
      useViewStore.getState().setViewport({ widthPx: widthRef.current, duration: audio.duration });
      useViewStore.getState().fit({ widthPx: widthRef.current, duration: audio.duration });
    }
  }, [audio]);

  // strip 描画ループ。
  useEffect(() => {
    const canvas = stripRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    let scheduled = false;
    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const surface = { width: widthRef.current, height: STRIP_H };
      const view = useViewStore.getState();
      const pb = usePlaybackStore.getState();
      // 再生中の自動スクロール。
      if (pb.playing && audio) {
        const px = timeToX(pb.currentTime, view);
        if (px > surface.width * 0.92 || px < 0) {
          useViewStore
            .getState()
            .scrollTo(pb.currentTime, { widthPx: surface.width, duration: audio.duration });
        }
      }
      drawWaveform(ctx, surface, palette, audio, view);
      if (useModeStore.getState().mode === "annotation") {
        const cov = useCoverageStore.getState();
        drawCoverage(ctx, surface, palette, view, cov.heard, BUCKET_SEC);
      }
      drawPlayhead(ctx, surface, palette, view, pb.currentTime);
    };
    const requestDraw = () => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        draw();
      });
    };
    requestStripRef.current = requestDraw;
    requestDraw();

    const unsubs = [
      useViewStore.subscribe(requestDraw),
      usePlaybackStore.subscribe(requestDraw),
      useCoverageStore.subscribe(requestDraw),
      useModeStore.subscribe(requestDraw),
    ];
    return () => {
      for (const u of unsubs) u();
      requestStripRef.current = () => {};
    };
  }, [audio, palette]);

  // lanes 描画ループ。
  useEffect(() => {
    const canvas = lanesRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    let scheduled = false;
    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const surface = { width: widthRef.current, height: lanesH };
      const view = useViewStore.getState();
      const ed = useEditorStore.getState();
      const pb = usePlaybackStore.getState();
      drawLanesBg(ctx, surface, palette, laneN);
      const showStatus = useModeStore.getState().mode === "annotation";
      const now = performance.now();
      detectPulses(ed.segments, now); // ok→intruder/boundary の遷移にパルスを仕込む
      drawSegments(
        ctx,
        surface,
        palette,
        view,
        ed.segments,
        ed.selectedIds,
        ed.speakers,
        showStatus,
        (id) => pulseAlpha(id, now),
      );
      const rect = previewRef.current;
      if (rect) {
        const speakers = useEditorStore.getState().speakers;
        const laneIdx = rect.createSpeaker != null ? laneOf(rect.createSpeaker, speakers) : null;
        const y0 = laneIdx != null ? (laneIdx * lanesH) / laneCount(speakers) : 0;
        const h = laneIdx != null ? lanesH / laneCount(speakers) : surface.height;
        drawSelectionRect(ctx, surface, palette, rect.x0, rect.x1, y0, h);
      }
      drawPlayhead(ctx, surface, palette, view, pb.currentTime);
      if (hasActivePulses()) requestLanesRef.current(); // パルスが残る間だけ次フレームを要求
    };
    const requestDraw = () => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        draw();
      });
    };
    requestLanesRef.current = requestDraw;
    requestDraw();

    const unsubs = [
      useViewStore.subscribe(requestDraw),
      useEditorStore.subscribe(requestDraw),
      usePlaybackStore.subscribe(requestDraw),
      useModeStore.subscribe(requestDraw),
    ];
    return () => {
      for (const u of unsubs) u();
      requestLanesRef.current = () => {};
    };
  }, [palette, lanesH, laneN]);

  // ホイール: ⌘/Ctrl=ズーム, 横/Shift=時間パン, 縦=レーンの縦スクロール
  // (はみ出ていない時のみ縦=ズーム)。wrapper div に passive:false で登録。
  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    const onWheel = (e: WheelEvent) => {
      if (!audio) return;
      const vp: Viewport = { widthPx: widthRef.current, duration: audio.duration };
      const zoomAt = (intensity: number) => {
        const rect = wrapper.getBoundingClientRect();
        const anchorX = e.clientX - rect.left;
        useViewStore.getState().zoomAt(anchorX, Math.exp(-e.deltaY * intensity), vp);
      };

      // ピンチ (⌘/Ctrl) = ズーム
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        zoomAt(0.02);
        return;
      }
      // 横方向 / Shift = 時間軸パン
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        e.preventDefault();
        useViewStore.getState().pan(e.shiftKey ? e.deltaY || e.deltaX : e.deltaX, vp);
        return;
      }
      // 縦ホイール: レーンがはみ出ていればネイティブ縦スクロール (波形は sticky で固定)。
      // はみ出ていなければ従来どおりズーム。
      const canScrollLanes = wrapper.scrollHeight > wrapper.clientHeight + 1;
      if (canScrollLanes) return; // preventDefault せず → 内部スクロール
      e.preventDefault();
      zoomAt(0.008);
    };
    wrapper.addEventListener("wheel", onWheel, { passive: false });
    return () => wrapper.removeEventListener("wheel", onWheel);
  }, [audio]);

  const localX = (e: { clientX: number }): number =>
    e.clientX - (lanesRef.current?.getBoundingClientRect().left ?? 0);
  const localY = (e: { clientY: number }): number =>
    e.clientY - (lanesRef.current?.getBoundingClientRect().top ?? 0);

  const onPointerDown = (e: ReactPointerEvent) => {
    if (!audio) return;
    lanesRef.current?.setPointerCapture(e.pointerId);
    const view = useViewStore.getState();
    const ed = useEditorStore.getState();
    const x = localX(e);
    const y = localY(e);
    const t = xToTime(x, view);

    let mode: EditMode;
    let origSeg: Segment | null = null;
    let createSpeaker: string | null = null;
    if (e.shiftKey) {
      mode = "range";
    } else if (e.metaKey || e.ctrlKey) {
      mode = "select-toggle";
    } else {
      const hit = hitSegment(ed.segments, view, x, y, ed.speakers, lanesH);
      if (hit) {
        mode = hit.mode;
        origSeg = hit.seg;
        ed.selectSingle(hit.seg.id);
      } else {
        mode = "create";
        createSpeaker = speakerAtY(y, ed.speakers, lanesH);
      }
    }
    dragRef.current = {
      startX: x,
      startY: y,
      startTime: t,
      mode,
      origSeg,
      createSpeaker,
      additive: e.metaKey || e.ctrlKey,
      moved: false,
      began: false,
    };
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    const view = useViewStore.getState();
    const drag = dragRef.current;
    const x = localX(e);

    if (!drag) {
      const canvas = lanesRef.current;
      if (!canvas || !audio) return;
      const ed = useEditorStore.getState();
      const hit = hitSegment(ed.segments, view, x, localY(e), ed.speakers, lanesH);
      canvas.style.cursor = !hit ? "crosshair" : hit.mode === "move" ? "move" : "ew-resize";
      return;
    }

    const movedX = Math.abs(x - drag.startX) > 3;
    const movedY = drag.mode === "move" && Math.abs(localY(e) - drag.startY) > 3;
    if (movedX || movedY) drag.moved = true;
    if (!drag.moved) return;
    const ed = useEditorStore.getState();
    const duration = audio?.duration ?? 0;

    if (drag.mode === "range" || drag.mode === "create") {
      previewRef.current = { x0: drag.startX, x1: x, createSpeaker: drag.createSpeaker };
      requestLanesRef.current();
      return;
    }

    if (drag.origSeg && (drag.mode === "move" || drag.mode.startsWith("resize"))) {
      if (!drag.began) {
        if (drag.mode.startsWith("resize")) ed.beginResize();
        else ed.beginEdit();
        drag.began = true;
      }
      const t = xToTime(x, view);
      const base = drag.origSeg;
      let edited: Segment;
      if (drag.mode === "move") {
        // 横=時間移動, 縦=別レーン(話者)へ付け替え。
        const movedSeg = moveSegment(base, t - drag.startTime, duration);
        const targetSpeaker = speakerAtY(localY(e), ed.speakers, lanesH);
        edited =
          targetSpeaker && targetSpeaker !== movedSeg.speaker
            ? { ...movedSeg, speaker: targetSpeaker }
            : movedSeg;
      } else {
        edited = drag.mode === "resize-start" ? resizeStart(base, t) : resizeEnd(base, t, duration);
      }
      const next = markEdited(edited);
      ed.applyLive(ed.segments.map((s) => (s.id === base.id ? next : s)));
    }
  };

  const onPointerUp = (e: ReactPointerEvent) => {
    const drag = dragRef.current;
    dragRef.current = null;
    previewRef.current = null;
    lanesRef.current?.releasePointerCapture(e.pointerId);
    if (!drag || !audio) return;

    const view = useViewStore.getState();
    const ed = useEditorStore.getState();
    const x = localX(e);
    const duration = audio.duration;

    if (drag.mode === "range" && drag.moved) {
      const lo = xToTime(Math.min(drag.startX, x), view);
      const hi = xToTime(Math.max(drag.startX, x), view);
      const ids = ed.segments.filter((s) => overlapsRange(s, lo, hi)).map((s) => s.id);
      if (drag.additive) ed.addToSelection(ids);
      else ed.setSelection(ids);
      requestLanesRef.current();
      return;
    }

    if (drag.mode === "create") {
      if (drag.moved) {
        const speaker = drag.createSpeaker ?? ed.activeSpeaker ?? ed.speakers[0] ?? "SPEAKER_00";
        const seg = createSegment(newId(), drag.startTime, xToTime(x, view), speaker, duration);
        ed.addSegment(seg);
      } else {
        ed.clearSelection();
        container.playback.seek(xToTime(x, view));
      }
      requestLanesRef.current();
      return;
    }

    if (drag.mode === "move" && drag.began && drag.origSeg && drag.moved) {
      const finalSeg = ed.segments.find((s) => s.id === drag.origSeg?.id);
      const ops = useEditOpsStore.getState();
      if (finalSeg?.speaker !== drag.origSeg.speaker) ops.inc("reassign");
      else ops.inc("resize");
    }

    if (drag.mode === "select-toggle" && !drag.moved) {
      const hit = hitSegment(ed.segments, view, x, localY(e), ed.speakers, lanesH);
      if (hit) ed.toggleSelect(hit.seg.id);
      else ed.clearSelection();
    }
    requestLanesRef.current();
  };

  // レーンのダブルクリック: 区間上なら区間再生、空きなら その位置から通常再生。
  const onDoubleClick = (e: { clientX: number; clientY: number }) => {
    if (!audio) return;
    const view = useViewStore.getState();
    const ed = useEditorStore.getState();
    const hit = hitSegment(ed.segments, view, localX(e), localY(e), ed.speakers, lanesH);
    if (hit) container.playback.playRegion(hit.seg.start, hit.seg.end);
    else container.playback.playFrom(xToTime(localX(e), view));
  };

  // 波形ストリップのダブルクリック: その位置から通常再生。
  const onStripDoubleClick = (e: { clientX: number }) => {
    if (!audio) return;
    const left = stripRef.current?.getBoundingClientRect().left ?? 0;
    container.playback.playFrom(xToTime(e.clientX - left, useViewStore.getState()));
  };

  return (
    <div className="waveform">
      <div className="waveform__toolbar">
        <button
          type="button"
          className="btn"
          disabled={!audio}
          onClick={() => useViewStore.getState().zoomButton(1 / ZOOM_STEP, viewport())}
        >
          −
        </button>
        <button
          type="button"
          className="btn"
          disabled={!audio}
          onClick={() => useViewStore.getState().zoomButton(ZOOM_STEP, viewport())}
        >
          ＋
        </button>
        <button
          type="button"
          className="btn"
          disabled={!audio}
          onClick={() => useViewStore.getState().fit(viewport())}
        >
          全体
        </button>
        <span className="faint" style={{ marginLeft: "auto", fontSize: "0.7rem" }}>
          空きドラッグ=作成 / 端=リサイズ / 本体=移動 (縦=話者変更) /
          波形ダブルクリック=ここから再生 / Shift+&lt;&gt;=再生速度
        </span>
      </div>
      {/* 波形ストリップは sticky で固定し、レーンが多いとこの枠内だけ縦スクロール */}
      <div
        ref={wrapperRef}
        className="waveform__canvas-wrap"
        style={{ maxHeight: `min(70vh, ${STRIP_H + MAX_VISIBLE_LANES * LANE_H}px)` }}
      >
        <canvas
          ref={stripRef}
          className="waveform__strip"
          style={{ width: "100%", height: STRIP_H, display: "block", cursor: "pointer" }}
          onDoubleClick={onStripDoubleClick}
        />
        {/* 話者レーン: 話者が増えると縦に伸びスクロール */}
        <canvas
          ref={lanesRef}
          style={{ width: "100%", height: Math.max(lanesH, LANE_H), display: "block" }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onDoubleClick={onDoubleClick}
        />
      </div>
    </div>
  );
}
