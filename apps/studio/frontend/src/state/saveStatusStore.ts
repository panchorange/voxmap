// autosave の保存ステータス表示 (非侵襲)。Google Docs 風に、ヘッダ隅へ控えめに出す。
// - 自動保存中: "保存中…" / 保存済み: "✓ HH:MM に保存" を常駐表示 (トーストではない)。
// - 手動 (Cmd/Ctrl+S) 時のみ emphatic=true で一瞬 ✓ を強調 → すぐ地味な timestamp に落ち着く。
// 時刻は呼び出し側 (autosave) から注入し、store は純粋に保ってテストしやすくする。

import { create } from "zustand";

export type SaveStatus = "idle" | "saving" | "saved" | "error";

interface SaveStatusState {
  status: SaveStatus;
  /** 最後に保存できた時刻 (epoch ms)。null = 未保存。 */
  savedAt: number | null;
  /** 直近の保存が手動 (Cmd/Ctrl+S) なら true。表示の一瞬強調に使う。 */
  emphatic: boolean;

  markSaving(): void;
  /** 保存成功。manual=true で手動保存 (強調表示)。 */
  markSaved(savedAt: number, manual?: boolean): void;
  markError(): void;
}

export const useSaveStatusStore = create<SaveStatusState>((set) => ({
  status: "idle",
  savedAt: null,
  emphatic: false,

  markSaving() {
    set({ status: "saving" });
  },
  markSaved(savedAt, manual = false) {
    set({ status: "saved", savedAt, emphatic: manual });
  },
  markError() {
    set({ status: "error" });
  },
}));
