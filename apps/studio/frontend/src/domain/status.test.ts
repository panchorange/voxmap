import { describe, expect, test } from "bun:test";
import {
  countByStatus,
  hasUnverified,
  markConfirmed,
  markEdited,
  statusToProvenance,
  unverified,
} from "./status.ts";
import type { Segment } from "./types.ts";

const seg = (id: string, status: Segment["status"]): Segment => ({
  id,
  start: 0,
  end: 1,
  speaker: "SPEAKER_00",
  status,
});

describe("markEdited", () => {
  test("auto -> edited", () => {
    expect(markEdited(seg("a", "auto")).status).toBe("edited");
  });
  test("edited / confirmed は不変", () => {
    expect(markEdited(seg("a", "edited")).status).toBe("edited");
    expect(markEdited(seg("a", "confirmed")).status).toBe("confirmed");
  });
});

describe("markConfirmed", () => {
  test("常に confirmed", () => {
    expect(markConfirmed(seg("a", "auto")).status).toBe("confirmed");
    expect(markConfirmed(seg("a", "edited")).status).toBe("confirmed");
  });
});

describe("hasUnverified / unverified", () => {
  test("auto が1件でもあれば true", () => {
    const segs = [seg("a", "confirmed"), seg("b", "auto")];
    expect(hasUnverified(segs)).toBe(true);
    expect(unverified(segs).map((s) => s.id)).toEqual(["b"]);
  });
  test("auto が無ければ false", () => {
    expect(hasUnverified([seg("a", "edited"), seg("b", "confirmed")])).toBe(false);
  });
});

describe("statusToProvenance", () => {
  test("マッピング", () => {
    expect(statusToProvenance("auto")).toBe("auto");
    expect(statusToProvenance("edited")).toBe("human_edited");
    expect(statusToProvenance("confirmed")).toBe("human_confirmed");
  });
});

describe("countByStatus", () => {
  test("件数集計", () => {
    const segs = [seg("a", "auto"), seg("b", "auto"), seg("c", "confirmed")];
    expect(countByStatus(segs)).toEqual({ auto: 2, edited: 0, confirmed: 1 });
  });
});
