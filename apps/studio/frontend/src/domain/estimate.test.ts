import { describe, expect, it } from "bun:test";
import { estimateDiarizeSec, RTF_FALLBACK, rtfFor } from "./estimate.ts";

describe("rtfFor", () => {
  it("matches device prefix (cuda:0 → cuda)", () => {
    expect(rtfFor("cuda:0")).toBe(0.01);
    expect(rtfFor("mps")).toBe(0.03);
    expect(rtfFor("cpu")).toBe(0.3);
  });
  it("falls back for null/unknown device", () => {
    expect(rtfFor(null)).toBe(RTF_FALLBACK);
    expect(rtfFor("xpu")).toBe(RTF_FALLBACK);
  });
});

describe("estimateDiarizeSec", () => {
  it("scales by device RTF and rounds", () => {
    expect(estimateDiarizeSec(2000, "mps")).toBe(60); // 2000 * 0.03
    expect(estimateDiarizeSec(1000, "cpu")).toBe(300);
  });
  it("enforces a floor", () => {
    expect(estimateDiarizeSec(10, "cuda")).toBe(5); // 10 * 0.01 = 0.1 → floor 5
  });
});
