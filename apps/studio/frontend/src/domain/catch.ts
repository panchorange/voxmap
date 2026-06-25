// キャッチトライアル (phantom): 自動分離結果の無音ギャップに「偽の発話」を仕込み、
// アノテーターが無検証で素通りしないかを試す。純粋関数 (id 採番は呼び出し側)。
//
// 判定 (1 phantom あたり):
//   - 削除された           → caught (罠に気付いた)
//   - status が auto 以外   → kept   (聴いて発話ありと判断 = 正当かもしれない)
//   - auto のまま残存       → missed (無検証で素通り = 失敗)
// kept は「正当な判断」か「一括confirmの判子押し」か区別できないため summary に記録する。
import { MIN_SEG } from "./constants.ts";
import type { Segment } from "./types.ts";

export interface CatchTrial {
  id: string;
  /** 仕込んだ phantom セグメントの id。 */
  segmentId: string;
  kind: "phantom";
}

export type CatchOutcome = "caught" | "kept" | "missed";

/** phantom を1つ仕込むのに必要な最小ギャップ長 (秒)。 */
const MIN_GAP = 1.0;
/** phantom セグメントの長さ (秒)。 */
const PHANTOM_LEN = 0.8;
/** 仕込む phantom 個数の上限。 */
const MAX_CATCH = 8;
/** 何秒ごとに phantom 1個を狙うか。 */
const CATCH_PER_SEC = 300;

/**
 * 音声長に比例した phantom 個数 (B案)。5分ごとに1個、上限 8。
 * 長尺でも検出力が落ちないようにする。
 */
export function catchCount(duration: number): number {
  if (duration <= 0) return 0;
  return Math.min(MAX_CATCH, Math.max(1, Math.ceil(duration / CATCH_PER_SEC)));
}

interface Gap {
  start: number;
  end: number;
}

/** セグメント和集合の補集合 = 発話の無い区間。lane 跨ぎの重なりも考慮する。 */
export function findGaps(segments: Segment[], duration: number): Gap[] {
  if (duration <= 0) return [];
  const sorted = [...segments].sort((a, b) => a.start - b.start);
  const gaps: Gap[] = [];
  let cursor = 0;
  for (const s of sorted) {
    if (s.start > cursor) gaps.push({ start: cursor, end: s.start });
    cursor = Math.max(cursor, s.end);
  }
  if (cursor < duration) gaps.push({ start: cursor, end: duration });
  return gaps;
}

/**
 * 大きいギャップから順に最大 count 個の phantom を仕込む。
 * 通常セグメントと見分けが付かないよう既存話者へ割り当てる。
 * @param mkId trial / segment の id 採番 (呼び出し側で crypto.randomUUID など)
 */
export function injectPhantoms(
  segments: Segment[],
  duration: number,
  count: number,
  speakers: string[],
  mkId: () => string,
): { segments: Segment[]; trials: CatchTrial[] } {
  if (count <= 0 || speakers.length === 0) return { segments, trials: [] };
  const gaps = findGaps(segments, duration)
    .filter((g) => g.end - g.start >= MIN_GAP)
    .sort((a, b) => b.end - b.start - (a.end - a.start))
    .slice(0, count);

  const phantoms: Segment[] = [];
  const trials: CatchTrial[] = [];
  gaps.forEach((g, i) => {
    const len = Math.min(PHANTOM_LEN, (g.end - g.start) * 0.5);
    if (len < MIN_SEG) return;
    const mid = (g.start + g.end) / 2;
    const segId = mkId();
    phantoms.push({
      id: segId,
      start: mid - len / 2,
      end: mid + len / 2,
      speaker: speakers[i % speakers.length] as string,
      status: "auto",
    });
    trials.push({ id: mkId(), segmentId: segId, kind: "phantom" });
  });
  return { segments: [...segments, ...phantoms], trials };
}

/** phantom ごとの結果。 */
export function outcomeOf(trial: CatchTrial, segments: Segment[]): CatchOutcome {
  const seg = segments.find((s) => s.id === trial.segmentId);
  if (!seg) return "caught";
  return seg.status === "auto" ? "missed" : "kept";
}

export interface CatchSummary {
  total: number;
  caught: number;
  kept: number;
  missed: number;
}

export function evaluateCatch(trials: CatchTrial[], segments: Segment[]): CatchSummary {
  const acc: CatchSummary = { total: trials.length, caught: 0, kept: 0, missed: 0 };
  for (const t of trials) acc[outcomeOf(t, segments)]++;
  return acc;
}

/**
 * confirmed のまま残った phantom セグメント (kept) を返す。
 * phantom は「基本は間違い (無音に挿入した偽発話)」前提なので、書き出し直前に
 * 「本当に発話があったか」を再確認させる対象。
 */
export function keptPhantoms(trials: CatchTrial[], segments: Segment[]): Segment[] {
  const ids = new Set(trials.map((t) => t.segmentId));
  return segments.filter((s) => ids.has(s.id) && s.status !== "auto");
}

/** 未検証 (auto) のまま残った phantom を出力から除く。最終正解を汚染しないため。 */
export function stripUntouchedPhantoms(segments: Segment[], trials: CatchTrial[]): Segment[] {
  const drop = new Set(
    trials
      .filter((t) => segments.find((s) => s.id === t.segmentId)?.status === "auto")
      .map((t) => t.segmentId),
  );
  return drop.size === 0 ? segments : segments.filter((s) => !drop.has(s.id));
}
