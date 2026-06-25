// RTTM の parse / serialize (仕様: 機能一覧.md 入出力)。純粋関数。
import type { Segment } from "./types.ts";

export interface ParsedRttm {
  /** RTTM 第2列のファイル識別子 (無ければ null) */
  fileId: string | null;
  segments: Segment[];
}

// SPEAKER 行のみ採用。start=field[3], dur=field[4], speaker=field[7]。end=start+dur。
export function parseRttm(text: string): ParsedRttm {
  const segments: Segment[] = [];
  let fileId: string | null = null;
  let i = 0;

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    const f = line.split(/\s+/);
    if (f[0] !== "SPEAKER") continue;

    const start = Number(f[3]);
    const dur = Number(f[4]);
    const speaker = f[7];
    if (!Number.isFinite(start) || !Number.isFinite(dur) || !speaker) continue;

    if (fileId === null && f[1] && f[1] !== "<NA>") fileId = f[1];
    segments.push({ id: `rttm-${i}`, start, end: start + dur, speaker, status: "auto" });
    i++;
  }
  return { fileId, segments };
}

// start 昇順・小数3桁で書き出す。
export function serializeRttm(segments: Segment[], fileId: string): string {
  return [...segments]
    .sort((a, b) => a.start - b.start)
    .map((s) => {
      const start = s.start.toFixed(3);
      const dur = (s.end - s.start).toFixed(3);
      return `SPEAKER ${fileId} 1 ${start} ${dur} <NA> <NA> ${s.speaker} <NA> <NA>`;
    })
    .join("\n");
}
