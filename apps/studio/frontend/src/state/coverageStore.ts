import { create } from "zustand";

// 再生済み区間を 0.1s バケットで記録する。アノテーションモードの「聴いたか」を可視化し、
// 確認 (confirm) の前提条件にも使う補助シグナル。倍速再生・シーク跨ぎはカウントしない。

export const BUCKET_SEC = 0.1;
/** これを超える時間ギャップはシーク跨ぎとみなし、間を埋めない。 */
const MAX_FILL_GAP = 0.3;

interface CoverageState {
  duration: number;
  heard: Uint8Array;
  heardCount: number;
  /** バケット集合が変わるたびに増える (描画トリガ用)。 */
  version: number;
  reset(duration: number): void;
  /** prevT→t を再生済みにする。rate>1 (倍速) は無視。 */
  mark(prevT: number, t: number, rate: number): void;
  percentHeard(): number;
  /** 区間 [start,end] が完全に再生済みか。 */
  heardSpan(start: number, end: number): boolean;
}

function bucketIndex(t: number, n: number): number {
  return Math.min(n - 1, Math.max(0, Math.floor(t / BUCKET_SEC)));
}

export const useCoverageStore = create<CoverageState>((set, get) => ({
  duration: 0,
  heard: new Uint8Array(0),
  heardCount: 0,
  version: 0,

  reset(duration) {
    const n = Math.max(1, Math.ceil(duration / BUCKET_SEC));
    set({ duration, heard: new Uint8Array(n), heardCount: 0, version: get().version + 1 });
  },

  mark(prevT, t, rate) {
    if (rate > 1.0001) return;
    const { heard } = get();
    const n = heard.length;
    if (n === 0) return;
    const lo = Math.min(prevT, t);
    const hi = Math.max(prevT, t);
    // シーク跨ぎ: 間を埋めず、着地点のバケットだけ。
    const from = hi - lo > MAX_FILL_GAP ? bucketIndex(t, n) : bucketIndex(lo, n);
    const to = bucketIndex(hi - lo > MAX_FILL_GAP ? t : hi, n);
    let added = 0;
    for (let i = from; i <= to; i++) {
      if (heard[i] === 0) {
        heard[i] = 1;
        added++;
      }
    }
    if (added > 0) {
      set((s) => ({ heardCount: s.heardCount + added, version: s.version + 1 }));
    }
  },

  percentHeard() {
    const { heard, heardCount } = get();
    return heard.length === 0 ? 0 : heardCount / heard.length;
  },

  heardSpan(start, end) {
    const { heard } = get();
    const n = heard.length;
    if (n === 0) return false;
    const from = bucketIndex(start, n);
    const to = bucketIndex(Math.max(start, end - 1e-6), n);
    for (let i = from; i <= to; i++) {
      if (heard[i] === 0) return false;
    }
    return true;
  },
}));
