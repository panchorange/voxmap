import { describe, expect, test } from "bun:test";
import {
  ACCEPTED_TOOLS,
  buildSidecar,
  parseSidecar,
  readSidecar,
  serializeSidecar,
} from "./sidecar.ts";
import type { Segment } from "./types.ts";

const seg = (start: number, status: Segment["status"]): Segment => ({
  id: `${start}`,
  start,
  end: start + 1,
  speaker: "SPEAKER_00",
  status,
});

describe("buildSidecar", () => {
  test("provenance 導出と summary 集計", () => {
    const out = buildSidecar({
      fileId: "ES2004a",
      mode: "annotation",
      segments: [seg(2, "edited"), seg(0, "confirmed"), seg(1, "auto")],
      percentHeard: 0.9266,
      catch: { total: 3, caught: 2, kept: 1, missed: 0 },
    });
    // start 昇順
    expect(out.segments.map((s) => s.start)).toEqual([0, 1, 2]);
    expect(out.segments.map((s) => s.provenance)).toEqual([
      "human_confirmed",
      "auto",
      "human_edited",
    ]);
    expect(out.summary.segmentCount).toBe(3);
    expect(out.summary.byStatus).toEqual({ auto: 1, edited: 1, confirmed: 1 });
    expect(out.summary.percentHeard).toBe(0.927); // 小数3桁丸め
    expect(out.summary.catchTrials.caught).toBe(2);
  });

  test("complete は auto が0件のとき true (導出値)", () => {
    const incomplete = buildSidecar({
      fileId: "x",
      mode: "annotation",
      segments: [seg(0, "auto"), seg(1, "confirmed")],
      percentHeard: 0,
      catch: { total: 0, caught: 0, kept: 0, missed: 0 },
    });
    expect(incomplete.summary.complete).toBe(false);
    const done = buildSidecar({
      fileId: "x",
      mode: "annotation",
      segments: [seg(0, "edited"), seg(1, "confirmed")],
      percentHeard: 0,
      catch: { total: 0, caught: 0, kept: 0, missed: 0 },
    });
    expect(done.summary.complete).toBe(true);
  });
});

describe("parseSidecar (savepoint 再開)", () => {
  const input = {
    fileId: "ES2004a",
    mode: "annotation",
    segments: [seg(0, "confirmed"), seg(1, "auto"), seg(2, "edited")],
    percentHeard: 0.5,
    catch: { total: 0, caught: 0, kept: 0, missed: 0 },
  };

  test("provenance → status を復元、改変なしなら tampered=false", () => {
    const text = serializeSidecar(input);
    const parsed = parseSidecar(text);
    expect(parsed).not.toBeNull();
    expect(parsed?.fileId).toBe("ES2004a");
    expect(parsed?.segments.map((s) => s.status)).toEqual(["confirmed", "auto", "edited"]);
    expect(parsed?.complete).toBe(false); // auto 1件
    expect(parsed?.tampered).toBe(false);
  });

  test("segment を手編集すると tampered=true", () => {
    const obj = JSON.parse(serializeSidecar(input));
    obj.segments[1].provenance = "human_confirmed"; // 罠を捏造
    const parsed = parseSidecar(JSON.stringify(obj));
    expect(parsed?.tampered).toBe(true);
  });

  test("voxmap.json でなければ null", () => {
    expect(parseSidecar('{"foo":1}')).toBeNull();
    expect(parseSidecar("not json")).toBeNull();
  });

  // 公開前 (repo 改名前) の studio は tool: "speaker-diarization-studio" で書き出していた。
  const legacy = (): string => {
    const obj = JSON.parse(serializeSidecar(input));
    obj.tool = "speaker-diarization-studio";
    return JSON.stringify(obj);
  };

  test("旧ツール名 (speaker-diarization-studio) の json も読み込める", () => {
    const parsed = parseSidecar(legacy());
    expect(parsed).not.toBeNull();
    expect(parsed?.fileId).toBe("ES2004a");
    expect(parsed?.segments.map((s) => s.status)).toEqual(["confirmed", "auto", "edited"]);
  });

  test("旧ツール名に差し替えただけなら tampered=false (integrity は tool を含まない)", () => {
    expect(parseSidecar(legacy())?.tampered).toBe(false);
  });

  test("書き出しは常に現行名 (旧名で書き出さない)", () => {
    const out = buildSidecar(input);
    expect(out.tool).toBe("voxmap-studio");
    expect(ACCEPTED_TOOLS).toEqual(["voxmap-studio", "speaker-diarization-studio"]);
  });

  test("exportedAt は任意", () => {
    const out = buildSidecar({
      fileId: "x",
      mode: "annotation",
      segments: [],
      percentHeard: 0,
      catch: { total: 0, caught: 0, kept: 0, missed: 0 },
    });
    expect(out.exportedAt).toBeUndefined();
  });

  test("audioName を保存・復元できる", () => {
    const text = serializeSidecar({ ...input, audioName: "ES2004a.Mix-Headset.wav" });
    const parsed = parseSidecar(text);
    expect(parsed?.audioName).toBe("ES2004a.Mix-Headset.wav");
  });

  test("audioName なしでも復元できる (後方互換)", () => {
    const text = serializeSidecar(input); // audioName 未指定
    const parsed = parseSidecar(text);
    expect(parsed?.audioName).toBeUndefined();
  });

  const cost = {
    activeSec: 2105,
    wallSec: 2297,
    audioSec: 2052.3,
    editOps: 330,
    editOpsDetail: { reassign: 10, resize: 50, split: 0, create: 266, del: 4 },
  };

  test("cost / createdAt を保存・復元できる (再開で積み増す元)", () => {
    const text = serializeSidecar({
      ...input,
      cost,
      createdAt: "2026-06-10T09:00:00.000Z",
    });
    const parsed = parseSidecar(text);
    expect(parsed?.cost).toEqual(cost);
    expect(parsed?.createdAt).toBe("2026-06-10T09:00:00.000Z");
  });

  test("cost / createdAt なしでも復元できる (v1/v2 後方互換)", () => {
    const parsed = parseSidecar(serializeSidecar(input));
    expect(parsed?.cost).toBeUndefined();
    expect(parsed?.createdAt).toBeUndefined();
  });

  test("cost が型不正なら undefined (壊れた JSON を握りつぶす)", () => {
    const obj = JSON.parse(serializeSidecar(input));
    obj.summary.cost = { activeSec: "nope" };
    const parsed = parseSidecar(JSON.stringify(obj));
    expect(parsed?.cost).toBeUndefined();
  });
});

// 読み込めない json は「何も起きない」ではなく理由を出す。理由の区別をここで固定する。
describe("readSidecar (拒否理由)", () => {
  const input = {
    fileId: "ES2004a",
    mode: "annotation",
    segments: [seg(0, "confirmed")],
    percentHeard: 0.5,
    catch: { total: 0, caught: 0, kept: 0, missed: 0 },
  };

  test("JSON として解析できない", () => {
    expect(readSidecar("not json")).toEqual({ ok: false, reject: { reason: "not-json" } });
  });

  test("トップレベルがオブジェクトでない", () => {
    expect(readSidecar("42")).toEqual({ ok: false, reject: { reason: "not-object" } });
    expect(readSidecar("null")).toEqual({ ok: false, reject: { reason: "not-object" } });
  });

  test("tool が非対応なら実際に入っていた値を返す", () => {
    expect(readSidecar('{"tool":"audacity","segments":[]}')).toEqual({
      ok: false,
      reject: { reason: "tool-mismatch", tool: "audacity" },
    });
  });

  test("tool が欠落 / 非文字列なら tool=null", () => {
    expect(readSidecar('{"segments":[]}')).toEqual({
      ok: false,
      reject: { reason: "tool-mismatch", tool: null },
    });
    expect(readSidecar('{"tool":123,"segments":[]}')).toEqual({
      ok: false,
      reject: { reason: "tool-mismatch", tool: null },
    });
    // 配列も typeof "object" なので tool 欠落として扱われる
    expect(readSidecar("[1,2]")).toEqual({
      ok: false,
      reject: { reason: "tool-mismatch", tool: null },
    });
  });

  test("segments が配列でない (tool は対応名)", () => {
    const obj = JSON.parse(serializeSidecar(input));
    obj.segments = "nope";
    expect(readSidecar(JSON.stringify(obj))).toEqual({
      ok: false,
      reject: { reason: "segments-not-array" },
    });
  });

  test("成功時は sidecar を返す (parseSidecar と同値)", () => {
    const text = serializeSidecar(input);
    const read = readSidecar(text);
    expect(read.ok).toBe(true);
    expect(read.ok ? read.sidecar : null).toEqual(parseSidecar(text));
  });

  test("旧ツール名も ok で返る", () => {
    const obj = JSON.parse(serializeSidecar(input));
    obj.tool = "speaker-diarization-studio";
    const read = readSidecar(JSON.stringify(obj));
    expect(read.ok).toBe(true);
    expect(read.ok && read.sidecar.tampered).toBe(false);
  });
});
