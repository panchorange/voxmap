// Canvas 描画 (純粋手続き)。色は CanvasPalette (テーマの CSS 変数) から受け取る。
import { RULER_H } from "../../domain/constants.ts";
import { timeToX, type View, xToTime } from "../../domain/coords.ts";
import { laneCount, laneHeight, laneOf } from "../../domain/lanes.ts";
import { speakerColor } from "../../domain/speaker.ts";
import type { DecodedAudio, Segment } from "../../domain/types.ts";
import { fmtTime } from "../../ui/format.ts";
import type { CanvasPalette } from "../../ui/theme/theme.ts";

/** 16進色 (#rrggbb) に alpha を付けて rgba 文字列にする。 */
function withAlpha(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  if (h.length !== 6) return hex;
  const r = Number.parseInt(h.slice(0, 2), 16);
  const g = Number.parseInt(h.slice(2, 4), 16);
  const b = Number.parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export interface Surface {
  width: number;
  height: number;
}

// ラベル間隔がおよそ 80px になる「きりの良い」秒数を選ぶ。
const NICE_STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
function niceTimeStep(pps: number): number {
  const raw = 80 / pps;
  for (const s of NICE_STEPS) {
    if (s >= raw) return s;
  }
  return NICE_STEPS[NICE_STEPS.length - 1] as number;
}

/** 波形ストリップ (ルーラー + 波形)。上部 sticky canvas に描く。 */
export function drawWaveform(
  ctx: CanvasRenderingContext2D,
  surface: Surface,
  palette: CanvasPalette,
  audio: DecodedAudio | null,
  view: View,
): void {
  const { width, height } = surface;

  ctx.fillStyle = palette.waveBg;
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = palette.rulerBg;
  ctx.fillRect(0, 0, width, RULER_H);

  if (!audio) return;

  const top = RULER_H;
  const waveH = height - RULER_H;
  const mid = top + waveH / 2;
  const amp = (waveH / 2) * 0.95;
  const { min, max, bps } = audio.peaks;

  // 波形 (1px 列ごとに min/max を縦線)
  ctx.strokeStyle = palette.segNoSpeaker;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let px = 0; px < width; px++) {
    const t = xToTime(px + 0.5, view);
    if (t < 0 || t > audio.duration) continue;
    const bi = Math.min(min.length - 1, Math.max(0, Math.floor(t * bps)));
    const lo = min[bi] ?? 0;
    const hi = max[bi] ?? 0;
    ctx.moveTo(px + 0.5, mid - hi * amp);
    ctx.lineTo(px + 0.5, mid - lo * amp);
  }
  ctx.stroke();

  // 中央線
  ctx.strokeStyle = palette.midline;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, mid);
  ctx.lineTo(width, mid);
  ctx.stroke();

  drawRuler(ctx, surface, palette, view);
}

/**
 * 再生カバレッジ帯。strip canvas の最下部に「再生済み」を塗る (annotation モード)。
 * heard は 0.1s バケットの Uint8Array。
 */
export function drawCoverage(
  ctx: CanvasRenderingContext2D,
  surface: Surface,
  palette: CanvasPalette,
  view: View,
  heard: Uint8Array,
  bucketSec: number,
): void {
  if (heard.length === 0) return;
  const barH = 4;
  const y = surface.height - barH;
  ctx.fillStyle = withAlpha(palette.midline, 0.25);
  ctx.fillRect(0, y, surface.width, barH);
  ctx.fillStyle = palette.playhead;
  for (let px = 0; px < surface.width; px++) {
    const t = xToTime(px + 0.5, view);
    if (t < 0) continue;
    const bi = Math.floor(t / bucketSec);
    if (bi >= heard.length) break;
    if (heard[bi]) ctx.fillRect(px, y, 1, barH);
  }
}

/** 再生ヘッド (canvas 全高に縦線)。strip / lanes 両方に呼ぶ。 */
export function drawPlayhead(
  ctx: CanvasRenderingContext2D,
  surface: Surface,
  palette: CanvasPalette,
  view: View,
  currentTime: number,
): void {
  const px = timeToX(currentTime, view);
  if (px < 0 || px > surface.width) return;
  ctx.strokeStyle = palette.playhead;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(px, 0);
  ctx.lineTo(px, surface.height);
  ctx.stroke();
}

/** 話者レーン領域の背景 (lanes canvas)。仕切り線のみ。 */
export function drawLanesBg(
  ctx: CanvasRenderingContext2D,
  surface: Surface,
  palette: CanvasPalette,
  n: number,
): void {
  ctx.fillStyle = palette.waveBg;
  ctx.fillRect(0, 0, surface.width, surface.height);

  const lh = laneHeight(surface.height, 0, n);
  ctx.strokeStyle = palette.grid;
  ctx.lineWidth = 1;
  for (let i = 1; i < n; i++) {
    const y = i * lh;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(surface.width, y);
    ctx.stroke();
  }
}

/**
 * 区間オーバーレイ。lanes canvas (top=0) に描く。
 * laneTop は lanes 内での y オフセット (通常 0)。
 */
export function drawSegments(
  ctx: CanvasRenderingContext2D,
  surface: Surface,
  palette: CanvasPalette,
  view: View,
  segments: Segment[],
  selectedIds: string[],
  speakerOrder: string[],
  // annotation モードのみ status の見た目を反映する (viewer は全て実線)。
  showStatus = false,
  // 怪しさワンショットパルスの強度 (0..1)。新たに怪しくなった瞬間だけ glow を足す。
  pulseAt?: (id: string) => number,
): void {
  const n = laneCount(speakerOrder);
  const lh = laneHeight(surface.height, 0, n);
  const selected = new Set(selectedIds);
  const singleSelected = selectedIds.length === 1;
  const pad = 1.5;

  ctx.font = "11px ui-sans-serif, system-ui";
  ctx.textBaseline = "top";

  for (const s of segments) {
    const x0 = timeToX(s.start, view);
    const x1 = timeToX(s.end, view);
    if (x1 < 0 || x0 > surface.width) continue;

    const lane = laneOf(s.speaker, speakerOrder);
    const y0 = lane * lh + pad;
    const h = lh - pad * 2;
    const color = speakerColor(s.speaker, speakerOrder, palette.speakers);
    const sel = selected.has(s.id);
    const w = Math.max(1, x1 - x0);
    // 未検証 (auto) は薄く + 破線で「まだ検証していない」を一目で示す。
    const isAuto = showStatus && s.status === "auto";

    ctx.fillStyle = withAlpha(color, sel ? 0.5 : isAuto ? 0.16 : 0.28);
    ctx.fillRect(x0, y0, w, h);

    ctx.strokeStyle = sel ? palette.segSelected : color;
    ctx.lineWidth = sel ? 1.5 : showStatus && s.status === "confirmed" ? 1.5 : 1;
    if (isAuto) ctx.setLineDash([4, 3]);
    ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, h - 1);
    if (isAuto) ctx.setLineDash([]);

    ctx.fillStyle = sel ? palette.segSelected : color;
    ctx.fillText(s.speaker, x0 + 4, y0 + 2);

    // 怪しさ地図: 混同していそうな区間をセマンティック色 (テーマ追従) で強調。
    // 話者色とは独立。区間全体を細枠でリングし、右上に三角フラグを立てる
    // (狭い区間でも見える / 文字フォント非依存)。intruder=danger赤, boundary=amber。
    const sus = s.suspicion;
    if (!sel && sus && sus.label !== "ok") {
      const mark = sus.label === "intruder" ? palette.suspicionIntruder : palette.suspicionBoundary;
      // リング (区間外周)。話者色の枠を上書き。
      ctx.strokeStyle = mark;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([]);
      ctx.strokeRect(x0 + 0.75, y0 + 0.75, w - 1.5, h - 1.5);
      // 右上の三角フラグ。
      const fs = Math.min(8, w, h);
      if (fs >= 4) {
        ctx.fillStyle = mark;
        ctx.beginPath();
        ctx.moveTo(x1, y0);
        ctx.lineTo(x1 - fs, y0);
        ctx.lineTo(x1, y0 + fs);
        ctx.closePath();
        ctx.fill();
      }
      // ワンショット glow: 怪しくなった瞬間に外側へ広がる薄リング (1山で収束)。
      const a = pulseAt?.(s.id) ?? 0;
      if (a > 0) {
        const g = 3 * a; // 最大 3px 外側へ
        ctx.save();
        ctx.globalAlpha = 0.6 * a;
        ctx.strokeStyle = mark;
        ctx.lineWidth = 2;
        ctx.strokeRect(x0 + 0.75 - g, y0 + 0.75 - g, w - 1.5 + 2 * g, h - 1.5 + 2 * g);
        ctx.restore();
      }
    }

    if (singleSelected && sel) {
      ctx.fillStyle = palette.segSelected;
      ctx.fillRect(x0, y0, 4, h);
      ctx.fillRect(x1 - 4, y0, 4, h);
    }
  }
}

/** 範囲選択中のドラッグ矩形 (lanes canvas)。 */
export function drawSelectionRect(
  ctx: CanvasRenderingContext2D,
  surface: Surface,
  palette: CanvasPalette,
  x0: number,
  x1: number,
  y0 = 0,
  h = surface.height,
): void {
  const lo = Math.min(x0, x1);
  const w = Math.abs(x1 - x0);
  ctx.fillStyle = withAlpha(palette.segSelected, 0.12);
  ctx.fillRect(lo, y0, w, h);
  ctx.strokeStyle = withAlpha(palette.segSelected, 0.6);
  ctx.lineWidth = 1;
  ctx.strokeRect(lo + 0.5, y0 + 0.5, w - 1, h - 1);
}

function drawRuler(
  ctx: CanvasRenderingContext2D,
  surface: Surface,
  palette: CanvasPalette,
  view: View,
): void {
  const step = niceTimeStep(view.pps);
  const first = Math.ceil(view.offset / step) * step;
  ctx.fillStyle = palette.rulerText;
  ctx.strokeStyle = palette.grid;
  ctx.lineWidth = 1;
  ctx.font = "10px ui-sans-serif, system-ui";
  ctx.textBaseline = "top";

  for (let t = first; ; t += step) {
    const x = timeToX(t, view);
    if (x > surface.width) break;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, surface.height);
    ctx.stroke();
    ctx.fillText(fmtTime(t, step < 1), x + 3, 4);
  }
}
