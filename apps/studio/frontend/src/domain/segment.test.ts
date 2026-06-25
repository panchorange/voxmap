import { describe, expect, test } from "bun:test";
import { MIN_SEG } from "./constants.ts";
import { createSegment, moveSegment, resizeEnd, resizeStart, splitSegment } from "./segment.ts";
import type { Segment } from "./types.ts";

const seg: Segment = { id: "a", start: 2, end: 5, speaker: "SPEAKER_00", status: "auto" };

describe("createSegment", () => {
  test("normalizes order and clamps", () => {
    const s = createSegment("x", 5, 2, "A", 10);
    expect(s).toMatchObject({ start: 2, end: 5, speaker: "A" });
  });
  test("enforces minimum length", () => {
    const s = createSegment("x", 1, 1.001, "A", 10);
    expect(s.end - s.start).toBeCloseTo(MIN_SEG, 5);
  });
});

describe("moveSegment", () => {
  test("shifts keeping length", () => {
    expect(moveSegment(seg, 1, 10)).toMatchObject({ start: 3, end: 6 });
  });
  test("clamps to duration", () => {
    const s = moveSegment(seg, 100, 10);
    expect(s.end).toBe(10);
    expect(s.end - s.start).toBe(3);
  });
  test("clamps at zero", () => {
    expect(moveSegment(seg, -100, 10).start).toBe(0);
  });
});

describe("resize", () => {
  test("resizeStart keeps min length", () => {
    expect(resizeStart(seg, 4.999).start).toBeCloseTo(5 - MIN_SEG, 5);
  });
  test("resizeEnd keeps min length", () => {
    expect(resizeEnd(seg, 2.001, 10).end).toBeCloseTo(2 + MIN_SEG, 5);
  });
  test("resizeEnd clamps to duration", () => {
    expect(resizeEnd(seg, 100, 10).end).toBe(10);
  });
});

describe("splitSegment", () => {
  test("splits into two at t", () => {
    const r = splitSegment(seg, 3, "b");
    expect(r).not.toBeNull();
    expect(r?.[0]).toMatchObject({ id: "a", start: 2, end: 3 });
    expect(r?.[1]).toMatchObject({ id: "b", start: 3, end: 5 });
  });
  test("returns null when too close to an edge", () => {
    expect(splitSegment(seg, 2.001, "b")).toBeNull();
    expect(splitSegment(seg, 4.999, "b")).toBeNull();
  });
});
