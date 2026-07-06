import { describe, expect, it } from "bun:test";
import { DEFAULT_RATE, nextPlaybackRate, PLAYBACK_RATES } from "./playback.ts";

describe("nextPlaybackRate", () => {
  it("等速から1段上げ下げ", () => {
    expect(nextPlaybackRate(1, 1)).toBe(1.25);
    expect(nextPlaybackRate(1, -1)).toBe(0.75);
  });

  it("下端 0.25 でクランプ", () => {
    expect(nextPlaybackRate(0.25, -1)).toBe(0.25);
    expect(nextPlaybackRate(0.25, 1)).toBe(0.5);
  });

  it("上端 1.5 でクランプ", () => {
    expect(nextPlaybackRate(1.5, 1)).toBe(1.5);
    expect(nextPlaybackRate(1.5, -1)).toBe(1.25);
  });

  it("段に一致しない現在値は最近傍を基準にする", () => {
    // 0.6 は 0.5 に最近傍 → +1 で 0.75
    expect(nextPlaybackRate(0.6, 1)).toBe(0.75);
    // 2.0 は上端 1.5 に丸め → +1 でも 1.5 のまま
    expect(nextPlaybackRate(2.0, 1)).toBe(1.5);
  });

  it("全段を端から端まで辿れる", () => {
    let r = PLAYBACK_RATES[0] ?? DEFAULT_RATE;
    const seen = [r];
    for (let i = 0; i < PLAYBACK_RATES.length + 2; i++) {
      const n = nextPlaybackRate(r, 1);
      if (n !== r) seen.push(n);
      r = n;
    }
    expect(seen).toEqual([...PLAYBACK_RATES]);
  });

  it("既定は等速", () => {
    expect(DEFAULT_RATE).toBe(1);
    expect(PLAYBACK_RATES).toContain(DEFAULT_RATE);
  });
});
