// 編集操作カウンタ (評価設計 §4.2b)。
// 各カウンタはモデル出力のどの種類のミスをどれだけ修正したかを示す。
// - reassign : 話者IDの付け替え
// - resize   : 区間の端を動かす (開始/終了時刻の修正)
// - split    : 区間の分割
// - create   : 新規区間の作成
// - del      : 区間の削除
// セッション = 音声ロード〜書き出し。importSegments (= 音声ロード) でリセット。

import { create } from "zustand";

export interface EditOpsDetail {
  reassign: number;
  resize: number;
  split: number;
  create: number;
  del: number;
}

interface EditOpsState extends EditOpsDetail {
  /** 全カウンタの合計。 */
  total(): number;
  /** 音声ロード時にリセット。 */
  reset(): void;
  /** savepoint 再開時に保存済み内訳から復元する (以後の編集はこれに積む)。 */
  seed(detail: EditOpsDetail): void;
  inc(op: keyof EditOpsDetail): void;
}

export const useEditOpsStore = create<EditOpsState>((set, get) => ({
  reassign: 0,
  resize: 0,
  split: 0,
  create: 0,
  del: 0,

  total() {
    const s = get();
    return s.reassign + s.resize + s.split + s.create + s.del;
  },

  reset() {
    set({ reassign: 0, resize: 0, split: 0, create: 0, del: 0 });
  },

  seed(detail) {
    set({
      reassign: detail.reassign,
      resize: detail.resize,
      split: detail.split,
      create: detail.create,
      del: detail.del,
    });
  },

  inc(op) {
    set((s) => ({ [op]: s[op] + 1 }));
  },
}));
