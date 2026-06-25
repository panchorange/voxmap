// 話者ごとの横レーン (トラック) の幾何。重なり (同時刻に複数話者) を縦に並べて
// 個別に表示・編集できるようにする。各話者 = 1レーン。純粋関数。
import { LANE_H } from "./constants.ts";

/** レーン数 (最低1。話者ゼロでも1レーン確保して新規作成できるように)。 */
export function laneCount(speakers: string[]): number {
  return Math.max(1, speakers.length);
}

/** 話者レーン領域の総高さ (px)。1レーン固定高 × レーン数。 */
export function lanesHeight(n: number): number {
  return n * LANE_H;
}

/** 話者のレーン index (出現順)。未知話者は 0。 */
export function laneOf(speaker: string, speakers: string[]): number {
  const i = speakers.indexOf(speaker);
  return i < 0 ? 0 : i;
}

/** 1レーンの高さ (px)。top はルーラー下端。 */
export function laneHeight(totalHeight: number, top: number, n: number): number {
  return (totalHeight - top) / Math.max(1, n);
}

/** lane 番号の y 範囲 [y0, y1]。 */
export function laneYRange(
  lane: number,
  totalHeight: number,
  top: number,
  n: number,
): [number, number] {
  const h = laneHeight(totalHeight, top, n);
  const y0 = top + lane * h;
  return [y0, y0 + h];
}

/** y 座標がどのレーンか (範囲外はクランプ)。 */
export function laneAtY(y: number, totalHeight: number, top: number, n: number): number {
  const h = laneHeight(totalHeight, top, n);
  const lane = Math.floor((y - top) / h);
  return Math.min(n - 1, Math.max(0, lane));
}
