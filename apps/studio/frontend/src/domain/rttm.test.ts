import { describe, expect, test } from "bun:test";
import { parseRttm, serializeRttm } from "./rttm.ts";
import type { Segment } from "./types.ts";

describe("parseRttm", () => {
  test("parses SPEAKER lines and fileId", () => {
    const text = [
      "SPEAKER meeting1 1 0.500 1.250 <NA> <NA> SPEAKER_00 <NA> <NA>",
      "SPEAKER meeting1 1 2.000 0.750 <NA> <NA> SPEAKER_01 <NA> <NA>",
    ].join("\n");
    const { fileId, segments } = parseRttm(text);
    expect(fileId).toBe("meeting1");
    expect(segments).toHaveLength(2);
    expect(segments[0]).toMatchObject({ start: 0.5, end: 1.75, speaker: "SPEAKER_00" });
    expect(segments[1]).toMatchObject({ start: 2, end: 2.75, speaker: "SPEAKER_01" });
  });

  test("ignores non-SPEAKER lines and blanks", () => {
    const text = "# comment\n\nSPK foo\nSPEAKER f 1 0 1 <NA> <NA> A <NA> <NA>\n";
    expect(parseRttm(text).segments).toHaveLength(1);
  });

  test("skips malformed numeric fields", () => {
    const text = "SPEAKER f 1 abc 1 <NA> <NA> A <NA> <NA>";
    expect(parseRttm(text).segments).toHaveLength(0);
  });
});

describe("serializeRttm", () => {
  test("sorts by start and formats 3 decimals", () => {
    const segs: Segment[] = [
      { id: "b", start: 2, end: 2.75, speaker: "SPEAKER_01", status: "auto" },
      { id: "a", start: 0.5, end: 1.75, speaker: "SPEAKER_00", status: "auto" },
    ];
    const out = serializeRttm(segs, "meeting1").split("\n");
    expect(out[0]).toBe("SPEAKER meeting1 1 0.500 1.250 <NA> <NA> SPEAKER_00 <NA> <NA>");
    expect(out[1]).toBe("SPEAKER meeting1 1 2.000 0.750 <NA> <NA> SPEAKER_01 <NA> <NA>");
  });

  test("round-trips with parseRttm", () => {
    const text = "SPEAKER m 1 1.000 0.500 <NA> <NA> SPEAKER_00 <NA> <NA>";
    const { segments } = parseRttm(text);
    expect(serializeRttm(segments, "m")).toBe(text);
  });
});
