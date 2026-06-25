// 区間の編集操作。純粋関数 (id 採番のような副作用は呼び出し側が担う)。
import { MIN_SEG } from "./constants.ts";
import type { Segment } from "./types.ts";

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/**
 * 2 時刻から区間を生成。順序正規化 + 最小長 + [0,duration] クランプ。
 * 手描き新規は人の判断なので status=confirmed を既定とする。
 */
export function createSegment(
  id: string,
  t0: number,
  t1: number,
  speaker: string,
  duration: number,
  status: Segment["status"] = "confirmed",
): Segment {
  let start = clamp(Math.min(t0, t1), 0, duration);
  let end = clamp(Math.max(t0, t1), 0, duration);
  if (end - start < MIN_SEG) {
    end = Math.min(duration, start + MIN_SEG);
    start = Math.max(0, end - MIN_SEG);
  }
  return { id, start, end, speaker, status };
}

/** dt 秒ぶん平行移動 (長さ維持、[0,duration] 内にクランプ)。 */
export function moveSegment(seg: Segment, dt: number, duration: number): Segment {
  const len = seg.end - seg.start;
  const start = clamp(seg.start + dt, 0, Math.max(0, duration - len));
  return { ...seg, start, end: start + len };
}

/** 開始端をリサイズ (最小長を保つ)。 */
export function resizeStart(seg: Segment, newStart: number): Segment {
  return { ...seg, start: clamp(newStart, 0, seg.end - MIN_SEG) };
}

/** 終了端をリサイズ (最小長を保つ)。 */
export function resizeEnd(seg: Segment, newEnd: number, duration: number): Segment {
  return { ...seg, end: clamp(newEnd, seg.start + MIN_SEG, duration) };
}

/** 時刻 t で2分割。両断片が最小長を満たさなければ null。 */
export function splitSegment(seg: Segment, t: number, newId: string): [Segment, Segment] | null {
  if (t <= seg.start + MIN_SEG || t >= seg.end - MIN_SEG) return null;
  return [
    { ...seg, end: t },
    { ...seg, id: newId, start: t },
  ];
}
