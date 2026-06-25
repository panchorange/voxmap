import "fake-indexeddb/auto";
import { beforeEach, describe, expect, test } from "bun:test";
import { clear } from "idb-keyval";
import {
  DRAFT_LIMIT,
  type DraftRecord,
  deleteDraft,
  listDrafts,
  loadDraft,
  saveDraft,
  selectEvictions,
} from "./draftStore.ts";

function rec(fileId: string, savedAt: number): DraftRecord {
  return { fileId, sidecar: `{"id":"${fileId}"}`, savedAt };
}

describe("selectEvictions (純粋関数)", () => {
  test("上限以下なら何も削除しない", () => {
    expect(selectEvictions([rec("a", 1), rec("b", 2)], 5)).toEqual([]);
  });

  test("上限を超えたら古い順にあふれた分を返す", () => {
    const recs = [rec("a", 10), rec("b", 30), rec("c", 20), rec("d", 5)];
    const evicted = selectEvictions(recs, 2).map((r) => r.fileId);
    // 新しい順 b(30) c(20) を残し、古い a(10) d(5) を削除対象に
    expect(evicted.sort()).toEqual(["a", "d"]);
  });
});

describe("draftStore (IndexedDB roundtrip)", () => {
  beforeEach(async () => {
    await clear();
  });

  test("save → load で往復できる", async () => {
    await saveDraft(rec("meetingA", 100));
    const got = await loadDraft("meetingA");
    expect(got?.fileId).toBe("meetingA");
    expect(got?.savedAt).toBe(100);
  });

  test("同じ fileId は上書きされる", async () => {
    await saveDraft(rec("m", 1));
    await saveDraft(rec("m", 2));
    expect((await loadDraft("m"))?.savedAt).toBe(2);
    expect(await listDrafts()).toHaveLength(1);
  });

  test("listDrafts は savedAt の新しい順", async () => {
    await saveDraft(rec("old", 1));
    await saveDraft(rec("new", 3));
    await saveDraft(rec("mid", 2));
    expect((await listDrafts()).map((r) => r.fileId)).toEqual(["new", "mid", "old"]);
  });

  test("deleteDraft で消える", async () => {
    await saveDraft(rec("m", 1));
    await deleteDraft("m");
    expect(await loadDraft("m")).toBeUndefined();
  });

  test(`上限 (${DRAFT_LIMIT}) を超えると古いドラフトが LRU で削除される`, async () => {
    for (let i = 0; i < DRAFT_LIMIT + 2; i++) {
      await saveDraft(rec(`f${i}`, i + 1)); // savedAt 昇順 = f0 が最古
    }
    const remaining = (await listDrafts()).map((r) => r.fileId);
    expect(remaining).toHaveLength(DRAFT_LIMIT);
    // 最古の f0 / f1 は消え、新しい方が残る
    expect(remaining).not.toContain("f0");
    expect(remaining).not.toContain("f1");
    expect(remaining).toContain(`f${DRAFT_LIMIT + 1}`);
  });
});
