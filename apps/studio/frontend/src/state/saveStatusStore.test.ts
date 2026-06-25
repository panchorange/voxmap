import { beforeEach, describe, expect, test } from "bun:test";
import { useSaveStatusStore } from "./saveStatusStore.ts";

const st = () => useSaveStatusStore.getState();

describe("saveStatusStore", () => {
  beforeEach(() => {
    useSaveStatusStore.setState({ status: "idle", savedAt: null, emphatic: false });
  });

  test("初期は idle", () => {
    expect(st().status).toBe("idle");
    expect(st().savedAt).toBeNull();
  });

  test("markSaving → saving", () => {
    st().markSaving();
    expect(st().status).toBe("saving");
  });

  test("markSaved で savedAt を記録 (自動保存は emphatic=false)", () => {
    st().markSaved(1234);
    expect(st().status).toBe("saved");
    expect(st().savedAt).toBe(1234);
    expect(st().emphatic).toBe(false);
  });

  test("手動保存は emphatic=true", () => {
    st().markSaved(1234, true);
    expect(st().emphatic).toBe(true);
  });

  test("markError → error", () => {
    st().markSaving();
    st().markError();
    expect(st().status).toBe("error");
  });
});
