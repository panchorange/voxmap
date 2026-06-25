import { describe, expect, test } from "bun:test";
import type { Segment } from "../../domain/types.ts";
import { detectPulses, hasActivePulses, pulseAlpha } from "./suspicionPulse.ts";

function seg(id: string, label?: "intruder" | "boundary" | "ok"): Segment {
  return {
    id,
    start: 0,
    end: 1,
    speaker: "SPEAKER_00",
    status: "auto",
    ...(label
      ? { suspicion: { label, margin: label === "intruder" ? -0.1 : 0.3, nearest: null } }
      : {}),
  };
}

describe("suspicionPulse", () => {
  test("ok→intruder の遷移でパルスが立ち、1山で収束する", () => {
    // 初期 ok (基準)
    detectPulses([seg("a", "ok")], 0);
    expect(hasActivePulses()).toBe(false);

    // intruder に遷移 → パルス開始
    detectPulses([seg("a", "intruder")], 1000);
    expect(hasActivePulses()).toBe(true);
    expect(pulseAlpha("a", 1000)).toBeCloseTo(0, 5); // t=0 → 0
    expect(pulseAlpha("a", 1325)).toBeCloseTo(1, 1); // 中間 (~650/2) → ピーク

    // 期限切れで 0 になり掃除される
    expect(pulseAlpha("a", 2000)).toBe(0);
    expect(hasActivePulses()).toBe(false);
  });

  test("ラベル不変ならパルスは立たない", () => {
    detectPulses([seg("b", "intruder")], 0);
    pulseAlpha("b", 9999); // 掃除
    detectPulses([seg("b", "intruder")], 10_000); // intruder のまま
    expect(pulseAlpha("b", 10_000)).toBe(0); // 再点火しない
  });
});
