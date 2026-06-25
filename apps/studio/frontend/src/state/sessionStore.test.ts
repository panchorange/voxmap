import { beforeEach, describe, expect, test } from "bun:test";
import { IDLE_SEC, useSessionStore } from "./sessionStore.ts";

const sess = () => useSessionStore.getState();

// 1秒 tick を n 回まわす (nowMs は t0 から1秒ずつ進める)。playing は固定。
function runTicks(t0: number, n: number, playing: boolean): number {
  let now = t0;
  for (let i = 0; i < n; i++) {
    now += 1000;
    sess().tick(now, playing);
  }
  return now;
}

describe("sessionStore", () => {
  const ISO = "2026-06-13T00:00:00.000Z";

  beforeEach(() => {
    // singleton store をテスト間で分離する。前テストが残した resume 退避値を消してから開始。
    useSessionStore.setState({ resumeSec: 0, resumeCreatedAt: null, resumeWallSec: 0 });
    sess().start(0, ISO); // セッション開始 (t=0)
  });

  test("start でリセットされる", () => {
    runTicks(0, 5, true);
    expect(sess().activeSec).toBe(5);
    sess().start(10_000, ISO);
    expect(sess().activeSec).toBe(0);
    expect(sess().wallStartMs).toBe(10_000);
  });

  test("start は createdAt をスタンプする", () => {
    sess().start(0, ISO);
    expect(sess().createdAt).toBe(ISO);
  });

  test("resume → start で activeSec / createdAt を引き継ぐ (JSON→音声 順)", () => {
    // 音声未ロードの状態で savepoint を読み込む
    useSessionStore.setState({ wallStartMs: null });
    sess().resume(100, "2026-06-10T09:00:00.000Z");
    // 即反映される (音声を読み直さなくてもコストが復元される)
    expect(sess().activeSec).toBe(100);
    // かつ退避もされ、その後の音声ロード start() が 0 に戻さず引き継ぐ
    sess().start(5_000, ISO);
    expect(sess().activeSec).toBe(100);
    expect(sess().createdAt).toBe("2026-06-10T09:00:00.000Z");
    // 積み増しできる
    runTicks(5_000, 3, true);
    expect(sess().activeSec).toBe(103);
  });

  test("resume は音声を読み直さなくても activeSec / wallSec を即復元する (リロード後)", () => {
    // 自動保存復元後、音声ハンドルを読み直さない (start() が走らない) ケース。
    // editOps と同様、コスト値は 0 に落ちず保存値を保持しなければならない。
    useSessionStore.setState({ wallStartMs: null });
    sess().resume(660, "2026-06-10T09:00:00.000Z", 720);
    expect(sess().activeSec).toBe(660);
    expect(sess().createdAt).toBe("2026-06-10T09:00:00.000Z");
    expect(sess().wallSec(0)).toBe(720); // wallStartMs=null → priorWallSec をそのまま返す
  });

  test("resume は音声ロード済みなら即反映する (音声→JSON 順)", () => {
    runTicks(0, 4, true);
    expect(sess().activeSec).toBe(4);
    sess().resume(100, "2026-06-10T09:00:00.000Z");
    expect(sess().activeSec).toBe(100);
    expect(sess().createdAt).toBe("2026-06-10T09:00:00.000Z");
  });

  test("引き継ぎは one-shot (resume 無しの次セッションは 0 / 新 createdAt)", () => {
    useSessionStore.setState({ wallStartMs: null });
    sess().resume(100, "2026-06-10T09:00:00.000Z");
    sess().start(5_000, ISO); // 1回目: 引き継ぐ
    expect(sess().activeSec).toBe(100);
    sess().start(9_000, ISO); // 2回目: 別の新規音声 → リセット
    expect(sess().activeSec).toBe(0);
    expect(sess().createdAt).toBe(ISO);
  });

  test("createdAt 欠落 (旧 JSON) の resume は新 createdAt をスタンプ", () => {
    useSessionStore.setState({ wallStartMs: null });
    sess().resume(50); // createdAt 無し
    sess().start(5_000, ISO);
    expect(sess().activeSec).toBe(50);
    expect(sess().createdAt).toBe(ISO);
  });

  test("未開始 (wallStartMs=null) では加算しない", () => {
    useSessionStore.setState({ wallStartMs: null });
    runTicks(0, 3, true);
    expect(sess().activeSec).toBe(0);
  });

  test("操作直後は idle 以内なので加算する", () => {
    sess().markActivity(0);
    // 操作から IDLE_SEC 以内の tick は加算 (停止中でも)
    runTicks(0, IDLE_SEC, false);
    expect(sess().activeSec).toBe(IDLE_SEC);
  });

  test("無操作かつ停止中の放置 (idle) は加算しない", () => {
    sess().markActivity(0);
    // IDLE_SEC を超えると、停止中の tick は数えない
    const now = runTicks(0, IDLE_SEC + 10, false);
    expect(sess().activeSec).toBe(IDLE_SEC); // 以降の10秒は idle
    expect(now).toBe((IDLE_SEC + 10) * 1000);
  });

  test("再生中は無操作でも加算する (聴いている)", () => {
    sess().markActivity(0);
    runTicks(0, IDLE_SEC + 10, true); // ずっと再生中
    expect(sess().activeSec).toBe(IDLE_SEC + 10);
  });

  test("操作で idle タイマーが延びる", () => {
    sess().markActivity(0);
    runTicks(0, 10, false); // 10s 加算
    sess().markActivity(10_000); // 10s 時点で操作 → タイマー延長
    runTicks(10_000, 10, false); // さらに 10s 加算
    expect(sess().activeSec).toBe(20);
  });

  test("wallSec はロードからの経過", () => {
    expect(sess().wallSec(30_000)).toBe(30);
  });

  test("resume → start で wallSec は過去分に積み増す (再開で小さくならない)", () => {
    useSessionStore.setState({ wallStartMs: null });
    sess().resume(100, "2026-06-10T09:00:00.000Z", 1352);
    sess().start(0, ISO);
    // 過去分 1352 + 現セッション 30 秒
    expect(sess().wallSec(30_000)).toBe(1382);
  });
});
