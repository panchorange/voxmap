// セグメント検証状態の遷移・書き出しゲート判定・provenance 導出 (純粋関数)。
import type { Segment, SegmentStatus } from "./types.ts";

/** 書き出し時に各セグメントへ焼き込む来歴ラベル。 */
export type Provenance = "auto" | "human_edited" | "human_confirmed";

/** 編集 (境界/話者) を受けたら auto → edited に遷移。それ以外は不変。 */
export function markEdited(seg: Segment): Segment {
  return seg.status === "auto" ? { ...seg, status: "edited" } : seg;
}

/** 明示確認。常に confirmed にする。 */
export function markConfirmed(seg: Segment): Segment {
  return seg.status === "confirmed" ? seg : { ...seg, status: "confirmed" };
}

/** 未検証 (auto) が1件でも残っているか。A案ゲートの判定。 */
export function hasUnverified(segments: Segment[]): boolean {
  return segments.some((s) => s.status === "auto");
}

/** auto のセグメント (書き出しゲートのジャンプ先候補)。 */
export function unverified(segments: Segment[]): Segment[] {
  return segments.filter((s) => s.status === "auto");
}

/** status → provenance ラベル。 */
export function statusToProvenance(status: SegmentStatus): Provenance {
  switch (status) {
    case "auto":
      return "auto";
    case "edited":
      return "human_edited";
    case "confirmed":
      return "human_confirmed";
  }
}

/** provenance → status (voxmap.json 読み込みで再開するとき)。未知値は auto に倒す。 */
export function provenanceToStatus(provenance: string): SegmentStatus {
  switch (provenance) {
    case "human_edited":
      return "edited";
    case "human_confirmed":
      return "confirmed";
    default:
      return "auto";
  }
}

/** status 別の件数集計。 */
export function countByStatus(segments: Segment[]): Record<SegmentStatus, number> {
  const acc: Record<SegmentStatus, number> = { auto: 0, edited: 0, confirmed: 0 };
  for (const s of segments) acc[s.status]++;
  return acc;
}
