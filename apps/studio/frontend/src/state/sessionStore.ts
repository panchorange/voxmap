// セッションのコスト計測 (評価設計 §4.2a)。アノテーション1回の「アクティブ作業時間」を測る。
// - activeSec: idle を除いた作業秒。1秒 tick で、直近操作が IDLE_SEC 以内 **または** 再生中の
//   tick だけ加算する (無操作かつ停止中の放置は数えない)。
// - wallSec: 音声ロード〜現在の実時間 (参考値。wallStartMs から都度算出)。日跨ぎの総スパンは
//   createdAt〜exportedAt で別途追える (wallSec は現セッション分のみ)。
// セッション = 音声ロード〜書き出し。savepoint 再開は音声を読み直す = start() で新セッション。
//   ただし途中保存 JSON を読み込んだ場合は activeSec / createdAt を引き継ぐ (resume)。後から
//   音声ロードの start() が走っても消えないよう resumeSec / resumeCreatedAt に退避しておく。
// 時刻 (nowMs / nowIso) は呼び出し側 (wiring) から渡す。store は純粋に保ち単体テストしやすくする。

import { create } from "zustand";

/** 無操作とみなすまでの猶予 (秒)。これを超えて操作も再生も無い tick は加算しない。 */
export const IDLE_SEC = 10;

interface SessionState {
  /** idle を除いたアクティブ作業秒 (1秒 tick の積算。再開時は保存値から積み増す)。 */
  activeSec: number;
  /** 初回セッション開始時刻 (ISO)。再開時は保存値を引き継ぐ。null = 未開始。 */
  createdAt: string | null;
  /** 過去セッション分の実時間 (秒)。再開時に保存値を引き継ぎ、wallSec() に足す。 */
  priorWallSec: number;
  /** セッション開始時刻 (performance.now)。null = 未開始。 */
  wallStartMs: number | null;
  /** 直近の操作時刻 (performance.now)。 */
  lastActivityMs: number;
  /** 次の start() で activeSec に引き継ぐ保存値 (resume 用。consume 後 0)。 */
  resumeSec: number;
  /** 次の start() で createdAt に引き継ぐ保存値 (resume 用。consume 後 null)。 */
  resumeCreatedAt: string | null;
  /** 次の start() で priorWallSec に引き継ぐ保存値 (resume 用。consume 後 0)。 */
  resumeWallSec: number;

  /** 新セッション開始 (音声ロード時)。resume 退避値があれば引き継ぐ。 */
  start(nowMs: number, nowIso: string): void;
  /** savepoint JSON 読み込み時に保存済み activeSec / createdAt / wallSec を引き継ぐ。 */
  resume(savedActiveSec: number, savedCreatedAt?: string, savedWallSec?: number): void;
  /** 操作 (click/key/wheel) を記録。 */
  markActivity(nowMs: number): void;
  /** 1秒ごとの集計。直近操作が IDLE_SEC 以内、または再生中なら activeSec を1秒加算。 */
  tick(nowMs: number, playing: boolean): void;
  /** ロード〜現在の実時間 (秒)。 */
  wallSec(nowMs: number): number;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  activeSec: 0,
  createdAt: null,
  priorWallSec: 0,
  wallStartMs: null,
  lastActivityMs: 0,
  resumeSec: 0,
  resumeCreatedAt: null,
  resumeWallSec: 0,

  start(nowMs, nowIso) {
    set((s) => ({
      activeSec: s.resumeSec,
      createdAt: s.resumeCreatedAt ?? nowIso,
      priorWallSec: s.resumeWallSec,
      resumeSec: 0,
      resumeCreatedAt: null,
      resumeWallSec: 0,
      wallStartMs: nowMs,
      lastActivityMs: nowMs,
    }));
  },

  resume(savedActiveSec, savedCreatedAt, savedWallSec) {
    // 保存値は live state へ即反映する (editOps の seed と対称。音声を読み直さなくても
    // activeSec / createdAt / wallSec が復元され、コスト表示が 0 に落ちない)。
    // 未ロード時は、後続の音声ロード start() が resume* から引き継いで 0 に戻さないよう
    // 退避値も併せて残す (start() は activeSec を resumeSec で上書きするため)。
    set((s) => ({
      activeSec: savedActiveSec,
      createdAt: savedCreatedAt ?? s.createdAt,
      priorWallSec: savedWallSec ?? 0,
      ...(s.wallStartMs === null
        ? {
            resumeSec: savedActiveSec,
            resumeCreatedAt: savedCreatedAt ?? null,
            resumeWallSec: savedWallSec ?? 0,
          }
        : {}),
    }));
  },

  markActivity(nowMs) {
    set({ lastActivityMs: nowMs });
  },

  tick(nowMs, playing) {
    if (get().wallStartMs === null) return; // セッション未開始 (音声未ロード)
    const recentlyActive = nowMs - get().lastActivityMs <= IDLE_SEC * 1000;
    if (recentlyActive || playing) {
      set((s) => ({ activeSec: s.activeSec + 1 }));
    }
  },

  wallSec(nowMs) {
    const start = get().wallStartMs;
    // 過去セッション分 (priorWallSec) + 現セッションの経過。再開で小さくならない。
    return start === null ? get().priorWallSec : get().priorWallSec + (nowMs - start) / 1000;
  },
}));
