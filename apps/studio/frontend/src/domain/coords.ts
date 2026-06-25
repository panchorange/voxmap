// 時間 <-> 座標の変換とズーム/パンの数学。純粋関数のみ。
// 表示は pps (pixels per second) と offset (左端の時刻) で管理する。

import { PPS_MAX, PPS_MIN_FIT_RATIO } from "./constants.ts";

/** 表示状態 */
export interface View {
  /** pixels per second */
  pps: number;
  /** 左端の時刻 (秒) */
  offset: number;
}

/** 表示先の制約 */
export interface Viewport {
  /** 描画幅 (px) */
  widthPx: number;
  /** 音声全体の長さ (秒) */
  duration: number;
}

export function timeToX(t: number, view: View): number {
  return (t - view.offset) * view.pps;
}

export function xToTime(x: number, view: View): number {
  return view.offset + x / view.pps;
}

/** 現在の表示幅 (秒) */
export function viewWidthSec(view: View, widthPx: number): number {
  return widthPx / view.pps;
}

/** pps 下限 = フィット幅の PPS_MIN_FIT_RATIO 倍 */
export function minPps(viewport: Viewport): number {
  if (viewport.duration <= 0) {
    return PPS_MIN_FIT_RATIO;
  }
  return (viewport.widthPx / viewport.duration) * PPS_MIN_FIT_RATIO;
}

export function clampPps(pps: number, viewport: Viewport): number {
  return Math.min(PPS_MAX, Math.max(minPps(viewport), pps));
}

/** offset を [0, duration - 表示幅] にクランプ */
export function clampOffset(offset: number, view: View, viewport: Viewport): number {
  const widthSec = viewWidthSec(view, viewport.widthPx);
  const maxOffset = Math.max(0, viewport.duration - widthSec);
  return Math.min(maxOffset, Math.max(0, offset));
}

/**
 * anchorX (px) の時刻を固定点として factor 倍ズームする。
 * pps を [min, max] にクランプし、offset も範囲内へクランプする。
 */
export function zoomAt(view: View, anchorX: number, factor: number, viewport: Viewport): View {
  const anchorTime = xToTime(anchorX, view);
  const pps = clampPps(view.pps * factor, viewport);
  const zoomed: View = { pps, offset: anchorTime - anchorX / pps };
  return { pps, offset: clampOffset(zoomed.offset, zoomed, viewport) };
}

/** dx (px) ぶんパンする */
export function panBy(view: View, dxPx: number, viewport: Viewport): View {
  const offset = view.offset + dxPx / view.pps;
  return { ...view, offset: clampOffset(offset, view, viewport) };
}

/** 全体表示 (フィット) */
export function fit(viewport: Viewport): View {
  if (viewport.duration <= 0) {
    return { pps: 1, offset: 0 };
  }
  return { pps: viewport.widthPx / viewport.duration, offset: 0 };
}
