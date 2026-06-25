import { describe, expect, test } from "bun:test";
import {
  compactSpeakerNames,
  deriveSpeakerOrder,
  nextSpeakerName,
  overlapsRange,
  speakerColor,
  withRenamedSpeaker,
} from "./speaker.ts";
import type { Segment } from "./types.ts";

const seg = (start: number, end: number, speaker: string): Segment => ({
  id: `${start}`,
  start,
  end,
  speaker,
  status: "auto",
});

describe("compactSpeakerNames", () => {
  test("gap を詰める (02 削除後の 00,01,03,04 → 00,01,02,03)", () => {
    const segs = [seg(0, 1, "SPEAKER_00"), seg(1, 2, "SPEAKER_03"), seg(2, 3, "SPEAKER_04")];
    const r = compactSpeakerNames(segs, ["SPEAKER_00", "SPEAKER_01", "SPEAKER_03", "SPEAKER_04"]);
    expect(r.speakers).toEqual(["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03"]);
    expect(r.segments.map((s) => s.speaker)).toEqual(["SPEAKER_00", "SPEAKER_02", "SPEAKER_03"]);
    expect(r.map.get("SPEAKER_03")).toBe("SPEAKER_02");
    expect(r.map.get("SPEAKER_04")).toBe("SPEAKER_03");
  });
  test("詰める必要がなければ no-op (map 空)", () => {
    const r = compactSpeakerNames([], ["SPEAKER_00", "SPEAKER_01"]);
    expect(r.map.size).toBe(0);
    expect(r.speakers).toEqual(["SPEAKER_00", "SPEAKER_01"]);
  });
  test("custom 名は触らない", () => {
    const r = compactSpeakerNames([], ["Alice", "SPEAKER_02"]);
    expect(r.speakers).toEqual(["Alice", "SPEAKER_00"]);
  });
});

describe("deriveSpeakerOrder", () => {
  test("orders by first appearance, dedupes", () => {
    const segs = [seg(0, 1, "B"), seg(1, 2, "A"), seg(2, 3, "B")];
    expect(deriveSpeakerOrder(segs)).toEqual(["B", "A"]);
  });
  test("keeps existing first", () => {
    expect(deriveSpeakerOrder([seg(0, 1, "C")], ["A", "B"])).toEqual(["A", "B", "C"]);
  });
});

describe("speakerColor", () => {
  const palette = ["#111", "#222", "#333"];
  test("maps by index, cycles", () => {
    const order = ["A", "B", "C", "D"];
    expect(speakerColor("A", order, palette)).toBe("#111");
    expect(speakerColor("D", order, palette)).toBe("#111"); // 3 % 3 = 0
  });
  test("unknown -> first", () => {
    expect(speakerColor("X", ["A"], palette)).toBe("#111");
  });
});

describe("nextSpeakerName", () => {
  test("returns first unused SPEAKER_NN", () => {
    expect(nextSpeakerName([])).toBe("SPEAKER_00");
    expect(nextSpeakerName(["SPEAKER_00", "SPEAKER_01"])).toBe("SPEAKER_02");
    expect(nextSpeakerName(["SPEAKER_00", "SPEAKER_02"])).toBe("SPEAKER_01");
  });
});

describe("withRenamedSpeaker", () => {
  const segs = [seg(0, 1, "A"), seg(1, 2, "B"), seg(2, 3, "A")];
  test("renames in segments and order, preserves position", () => {
    const r = withRenamedSpeaker(segs, ["A", "B"], "A", "Alice");
    expect(r?.speakers).toEqual(["Alice", "B"]);
    expect(r?.segments.map((s) => s.speaker)).toEqual(["Alice", "B", "Alice"]);
  });
  test("no-op on empty / same / collision", () => {
    expect(withRenamedSpeaker(segs, ["A", "B"], "A", "  ")).toBeNull();
    expect(withRenamedSpeaker(segs, ["A", "B"], "A", "A")).toBeNull();
    expect(withRenamedSpeaker(segs, ["A", "B"], "A", "B")).toBeNull();
  });
  test("trims whitespace", () => {
    expect(withRenamedSpeaker(segs, ["A", "B"], "A", "  X ")?.speakers).toEqual(["X", "B"]);
  });
});

describe("overlapsRange", () => {
  test("true when overlapping", () => {
    expect(overlapsRange(seg(1, 3, "A"), 2, 5)).toBe(true);
  });
  test("false when disjoint / touching", () => {
    expect(overlapsRange(seg(1, 2, "A"), 2, 5)).toBe(false);
    expect(overlapsRange(seg(5, 6, "A"), 2, 5)).toBe(false);
  });
});
