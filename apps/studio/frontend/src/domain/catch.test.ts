import { describe, expect, test } from "bun:test";
import {
  catchCount,
  evaluateCatch,
  findGaps,
  injectPhantoms,
  keptPhantoms,
  outcomeOf,
  stripUntouchedPhantoms,
} from "./catch.ts";
import type { Segment } from "./types.ts";

const seg = (id: string, start: number, end: number, status: Segment["status"]): Segment => ({
  id,
  start,
  end,
  speaker: "SPEAKER_00",
  status,
});

// id を決定的に採番 (テスト用)。
function counter(): () => string {
  let i = 0;
  return () => `gen-${i++}`;
}

describe("catchCount", () => {
  test("5分ごとに1個、最低1・上限8", () => {
    expect(catchCount(0)).toBe(0);
    expect(catchCount(60)).toBe(1); // 1分 → 1
    expect(catchCount(300)).toBe(1); // 5分 → 1
    expect(catchCount(301)).toBe(2); // 5分超 → 2
    expect(catchCount(1500)).toBe(5); // 25分 → 5
    expect(catchCount(36000)).toBe(8); // 10時間 → 上限8
  });
});

describe("keptPhantoms", () => {
  test("auto 以外で残った phantom を返す", () => {
    const trials = [
      { id: "t0", segmentId: "p0", kind: "phantom" as const },
      { id: "t1", segmentId: "p1", kind: "phantom" as const },
      { id: "t2", segmentId: "p2", kind: "phantom" as const },
    ];
    const segments = [
      seg("p0", 1, 1.6, "confirmed"), // kept
      seg("p1", 5, 5.6, "auto"), // まだ未検証 → 除外
      seg("real", 8, 9, "confirmed"), // phantom でない
      // p2 は削除済み
    ];
    expect(keptPhantoms(trials, segments).map((s) => s.id)).toEqual(["p0"]);
  });
});

describe("findGaps", () => {
  test("セグメント間と末尾のギャップ", () => {
    const segs = [seg("a", 0, 2, "auto"), seg("b", 3, 4, "auto")];
    expect(findGaps(segs, 6)).toEqual([
      { start: 2, end: 3 },
      { start: 4, end: 6 },
    ]);
  });
  test("重なりを和集合で潰す", () => {
    const segs = [seg("a", 0, 3, "auto"), seg("b", 1, 2, "auto")];
    expect(findGaps(segs, 5)).toEqual([{ start: 3, end: 5 }]);
  });
});

describe("injectPhantoms", () => {
  test("大きいギャップに最大 count 個、既存話者で仕込む", () => {
    const segs = [seg("a", 0, 2, "auto"), seg("b", 10, 11, "auto")];
    const { segments, trials } = injectPhantoms(segs, 12, 3, ["SPEAKER_00"], counter());
    // ギャップは [2,10] と [11,12]。[11,12] は MIN_GAP(1.0) ちょうどで採用。
    expect(trials.length).toBe(2);
    expect(segments.length).toBe(4);
    for (const t of trials) {
      const ph = segments.find((s) => s.id === t.segmentId);
      expect(ph?.status).toBe("auto");
    }
  });
  test("話者ゼロなら仕込まない", () => {
    const { trials } = injectPhantoms([], 12, 3, [], counter());
    expect(trials.length).toBe(0);
  });
});

describe("outcomeOf / evaluateCatch", () => {
  const t0 = { id: "t0", segmentId: "p0", kind: "phantom" as const };
  const t1 = { id: "t1", segmentId: "p1", kind: "phantom" as const };
  const t2 = { id: "t2", segmentId: "p2", kind: "phantom" as const };
  const trials = [t0, t1, t2];

  test("削除=caught / 非auto=kept / auto残存=missed", () => {
    const segments = [
      // p0 は削除済み (存在しない)
      seg("p1", 5, 5.6, "confirmed"),
      seg("p2", 8, 8.6, "auto"),
    ];
    expect(outcomeOf(t0, segments)).toBe("caught");
    expect(outcomeOf(t1, segments)).toBe("kept");
    expect(outcomeOf(t2, segments)).toBe("missed");
    expect(evaluateCatch(trials, segments)).toEqual({
      total: 3,
      caught: 1,
      kept: 1,
      missed: 1,
    });
  });
});

describe("stripUntouchedPhantoms", () => {
  test("auto のまま残った phantom だけ除く", () => {
    const trials = [
      { id: "t0", segmentId: "p0", kind: "phantom" as const },
      { id: "t1", segmentId: "p1", kind: "phantom" as const },
    ];
    const segments = [
      seg("real", 0, 1, "confirmed"),
      seg("p0", 5, 5.6, "auto"), // 除かれる
      seg("p1", 8, 8.6, "confirmed"), // 残る (人が判断済み)
    ];
    const out = stripUntouchedPhantoms(segments, trials).map((s) => s.id);
    expect(out).toEqual(["real", "p1"]);
  });
});
