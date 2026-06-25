// 話者の順序と色解決。色はテーマ追従のため保持せず、出現順 index から
// パレット (CSS変数由来) を循環参照して解決する。純粋関数。
import type { Segment } from "./types.ts";

/** 区間の出現順に話者名を並べた配列を返す (existing を先頭に保つ)。 */
export function deriveSpeakerOrder(segments: Segment[], existing: string[] = []): string[] {
  const order = [...existing];
  for (const s of segments) {
    if (!order.includes(s.speaker)) order.push(s.speaker);
  }
  return order;
}

/** 話者名に対応する色を、出現順 index でパレットから循環解決する。 */
export function speakerColor(name: string, order: string[], palette: string[]): string {
  if (palette.length === 0) return "#888888";
  const i = order.indexOf(name);
  const idx = i < 0 ? 0 : i % palette.length;
  return palette[idx] ?? "#888888";
}

/** 範囲 [lo, hi] (秒) に重なる区間か (start < hi && end > lo)。 */
export function overlapsRange(seg: Segment, lo: number, hi: number): boolean {
  return seg.start < hi && seg.end > lo;
}

/**
 * 話者をリネームした segments / speakers を返す。順序は維持する。
 * 空・同名・既存話者との衝突 (誤マージ防止) は null (no-op)。
 */
export function withRenamedSpeaker(
  segments: Segment[],
  speakers: string[],
  oldName: string,
  newName: string,
): { segments: Segment[]; speakers: string[] } | null {
  const name = newName.trim();
  if (!name || name === oldName || speakers.includes(name)) return null;
  return {
    segments: segments.map((s) => (s.speaker === oldName ? { ...s, speaker: name } : s)),
    speakers: speakers.map((n) => (n === oldName ? name : n)),
  };
}

const AUTO_NAME_RE = /^SPEAKER_(\d+)$/;

/**
 * `SPEAKER_NN` 形式の話者名を、番号順に 00,01,02… へ詰める (gap を埋める)。
 * 例: [00,01,03,04] → [00,01,02,03]。リネーム済みの custom 名は対象外。
 * @returns 詰めた segments / speakers と、適用した old→new マップ (active 追従用)。
 */
export function compactSpeakerNames(
  segments: Segment[],
  speakers: string[],
): { segments: Segment[]; speakers: string[]; map: Map<string, string> } {
  const auto: { name: string; idx: number }[] = [];
  for (const name of speakers) {
    const m = AUTO_NAME_RE.exec(name);
    if (m?.[1] !== undefined) auto.push({ name, idx: Number(m[1]) });
  }
  auto.sort((a, b) => a.idx - b.idx);

  const map = new Map<string, string>();
  auto.forEach((x, i) => {
    const next = `SPEAKER_${String(i).padStart(2, "0")}`;
    if (next !== x.name) map.set(x.name, next);
  });
  if (map.size === 0) return { segments, speakers, map };

  const rename = (n: string): string => map.get(n) ?? n;
  return {
    segments: segments.map((s) => (map.has(s.speaker) ? { ...s, speaker: rename(s.speaker) } : s)),
    speakers: speakers.map(rename),
    map,
  };
}

/** 未使用の `SPEAKER_NN` を採番する。 */
export function nextSpeakerName(existing: string[]): string {
  const used = new Set(existing);
  for (let i = 0; ; i++) {
    const name = `SPEAKER_${String(i).padStart(2, "0")}`;
    if (!used.has(name)) return name;
  }
}
