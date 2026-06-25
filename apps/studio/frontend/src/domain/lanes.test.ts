import { describe, expect, test } from "bun:test";
import { LANE_H } from "./constants.ts";
import { laneAtY, laneCount, laneHeight, laneOf, lanesHeight, laneYRange } from "./lanes.ts";

describe("laneCount / laneOf", () => {
  test("at least 1 lane even with no speakers", () => {
    expect(laneCount([])).toBe(1);
    expect(laneCount(["A", "B"])).toBe(2);
  });
  test("laneOf is index, unknown -> 0", () => {
    expect(laneOf("B", ["A", "B"])).toBe(1);
    expect(laneOf("X", ["A", "B"])).toBe(0);
  });
});

describe("geometry", () => {
  // total 180, top 20 -> usable 160, n=2 -> 80 each
  test("laneHeight divides usable height", () => {
    expect(laneHeight(180, 20, 2)).toBe(80);
  });
  test("laneYRange", () => {
    expect(laneYRange(0, 180, 20, 2)).toEqual([20, 100]);
    expect(laneYRange(1, 180, 20, 2)).toEqual([100, 180]);
  });
  test("lanesHeight is fixed lane height times count", () => {
    expect(lanesHeight(2)).toBe(2 * LANE_H);
    expect(lanesHeight(5)).toBe(5 * LANE_H);
  });
  test("laneAtY clamps", () => {
    expect(laneAtY(30, 180, 20, 2)).toBe(0);
    expect(laneAtY(150, 180, 20, 2)).toBe(1);
    expect(laneAtY(-5, 180, 20, 2)).toBe(0);
    expect(laneAtY(9999, 180, 20, 2)).toBe(1);
  });
});
