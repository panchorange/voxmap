// 怪しさのワンショットパルス (案A)。segment が新たに intruder/boundary になった瞬間に
// ~650ms だけリングが光って収まる。常時アニメではないので CPU も目障り度も最小。
// 怪しさマークは canvas 描画なので、ここで強度 (0..1) だけ管理し render 側で glow を足す。

import type { Segment } from "../../domain/types.ts";

const PULSE_MS = 650;

const pulses = new Map<string, number>(); // segment id -> 開始時刻 (performance.now)
let prevLabel = new Map<string, string>(); // segment id -> 直近の怪しさラベル

function prefersReducedMotion(): boolean {
  return (
    typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * 現在の segments と前回を比べ、ok→intruder/boundary に変わった id にパルスを仕込む。
 * 描画ループの先頭で毎フレーム呼ぶ (ラベル不変なら何もしない)。
 * reduced-motion 時はパルスを仕込まない (ラベル追跡だけ更新)。
 */
export function detectPulses(segments: Segment[], now: number): void {
  const reduce = prefersReducedMotion();
  const next = new Map<string, string>();
  for (const s of segments) {
    const label = s.suspicion?.label ?? "ok";
    next.set(s.id, label);
    if (
      !reduce &&
      (label === "intruder" || label === "boundary") &&
      prevLabel.get(s.id) !== label
    ) {
      pulses.set(s.id, now);
    }
  }
  prevLabel = next;
}

/** id の今のパルス強度 (0..1..0 の1山)。期限切れは 0 を返し掃除する。 */
export function pulseAlpha(id: string, now: number): number {
  const start = pulses.get(id);
  if (start === undefined) return 0;
  const t = (now - start) / PULSE_MS;
  if (t >= 1) {
    pulses.delete(id);
    return 0;
  }
  return Math.sin(Math.PI * t); // 0 → 1 → 0 の単発バンプ
}

/** アニメ継続が必要か (描画ループが次フレームを要求するか)。 */
export function hasActivePulses(): boolean {
  return pulses.size > 0;
}
