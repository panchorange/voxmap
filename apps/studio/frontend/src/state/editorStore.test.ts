import { beforeEach, describe, expect, test } from "bun:test";
import type { Segment } from "../domain/types.ts";
import { useEditorStore } from "./editorStore.ts";

const ed = () => useEditorStore.getState();

function seg(id: string, speaker: string): Segment {
  return { id, start: 0, end: 1, speaker, status: "auto" };
}

describe("applySpeakerMapping (一括対応)", () => {
  beforeEach(() => {
    ed().importSegments(
      [seg("a", "SPEAKER_00"), seg("b", "SPEAKER_01"), seg("c", "SPEAKER_00")],
      "f1",
    );
  });

  test("複数クラスタを既知話者名へ一括リネームする", () => {
    ed().applySpeakerMapping([
      { from: "SPEAKER_00", to: "MEE071" },
      { from: "SPEAKER_01", to: "FEO070" },
    ]);
    const byId = Object.fromEntries(ed().segments.map((s) => [s.id, s.speaker]));
    expect(byId).toEqual({ a: "MEE071", b: "FEO070", c: "MEE071" });
    expect(ed().speakers).toEqual(["MEE071", "FEO070"]);
  });

  test("status は変えない (QA ゲートを迂回しない)", () => {
    ed().applySpeakerMapping([{ from: "SPEAKER_00", to: "MEE071" }]);
    expect(ed().segments.every((s) => s.status === "auto")).toBe(true);
  });

  test("1 履歴にまとまり undo で元に戻る", () => {
    ed().applySpeakerMapping([
      { from: "SPEAKER_00", to: "MEE071" },
      { from: "SPEAKER_01", to: "FEO070" },
    ]);
    ed().undo();
    expect(ed().segments.map((s) => s.speaker)).toEqual(["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]);
  });

  test("新規 (空ペア) のみなら no-op", () => {
    const before = ed().segments;
    ed().applySpeakerMapping([{ from: "SPEAKER_00", to: "SPEAKER_00" }]);
    expect(ed().segments).toBe(before); // 履歴も積まない
  });
});

describe("applySignals (編集追従の反映)", () => {
  beforeEach(() => {
    ed().importSegments([seg("a", "SPEAKER_00"), seg("b", "SPEAKER_01")], "f1");
  });

  test("非 null は上書き、null は既存値を保持", () => {
    // 先に a に怪しさを付与しておく
    ed().applySignals([
      {
        id: "a",
        suspicion: { label: "intruder", margin: -0.1, nearest: "SPEAKER_01" },
        recommendation: null,
      },
    ]);
    expect(ed().segments.find((s) => s.id === "a")?.suspicion?.label).toBe("intruder");

    // a は null (保持) / b は ok で上書き
    ed().applySignals([
      { id: "a", suspicion: null, recommendation: null },
      { id: "b", suspicion: { label: "ok", margin: 0.3, nearest: null }, recommendation: null },
    ]);
    expect(ed().segments.find((s) => s.id === "a")?.suspicion?.label).toBe("intruder"); // 保持
    expect(ed().segments.find((s) => s.id === "b")?.suspicion?.label).toBe("ok"); // 上書き
  });

  test("未知 id は無視、履歴も積まない", () => {
    const before = ed().segments;
    const pastLen = ed().past.length;
    ed().applySignals([
      { id: "zzz", suspicion: { label: "ok", margin: 0, nearest: null }, recommendation: null },
    ]);
    expect(ed().segments).toBe(before); // 変化なし (同一参照)
    expect(ed().past.length).toBe(pastLen); // 履歴を積まない
  });
});
