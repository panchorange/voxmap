import { describe, expect, test } from "bun:test";
import { PPS_MAX } from "./constants.ts";
import {
  clampOffset,
  clampPps,
  fit,
  panBy,
  timeToX,
  type View,
  type Viewport,
  xToTime,
  zoomAt,
} from "./coords.ts";

const view: View = { pps: 100, offset: 10 };
const viewport: Viewport = { widthPx: 1000, duration: 60 };

describe("timeToX / xToTime", () => {
  test("round-trips", () => {
    expect(timeToX(15, view)).toBe(500);
    expect(xToTime(500, view)).toBe(15);
  });
});

describe("clampPps", () => {
  test("upper bound", () => {
    expect(clampPps(99999, viewport)).toBe(PPS_MAX);
  });
  test("lower bound = fit * 0.6", () => {
    // fit pps = 1000/60 ≈ 16.67, min = *0.6 ≈ 10
    expect(clampPps(1, viewport)).toBeCloseTo((1000 / 60) * 0.6, 5);
  });
});

describe("clampOffset", () => {
  test("clamps to [0, duration - widthSec]", () => {
    // widthSec = 1000/100 = 10 -> maxOffset = 50
    expect(clampOffset(999, view, viewport)).toBe(50);
    expect(clampOffset(-5, view, viewport)).toBe(0);
  });
});

describe("zoomAt", () => {
  test("keeps anchor time fixed", () => {
    const anchorX = 300;
    const before = xToTime(anchorX, view);
    const zoomed = zoomAt(view, anchorX, 2, viewport);
    expect(xToTime(anchorX, zoomed)).toBeCloseTo(before, 5);
  });
  test("respects pps max", () => {
    const zoomed = zoomAt(view, 0, 9999, viewport);
    expect(zoomed.pps).toBe(PPS_MAX);
  });
});

describe("panBy", () => {
  test("shifts offset and clamps", () => {
    expect(panBy(view, 100, viewport).offset).toBe(11);
    expect(panBy(view, -99999, viewport).offset).toBe(0);
  });
});

describe("fit", () => {
  test("fills width", () => {
    const v = fit(viewport);
    expect(v.offset).toBe(0);
    expect(timeToX(viewport.duration, v)).toBeCloseTo(viewport.widthPx, 5);
  });
});
