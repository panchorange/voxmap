import { create } from "zustand";

/**
 * アプリモード。
 * - `viewer` (閲覧): 音声処理の出力を眺める用途。QA レイヤ (確認状態ゲート /
 *   カバレッジ / キャッチトライアル) はすべて無効。
 * - `annotation`: 正解データ作成用途。上記 QA がすべて有効。
 */
export type AppMode = "viewer" | "annotation";

const KEY = "voxmap-studio.mode";

function load(): AppMode {
  try {
    return localStorage.getItem(KEY) === "annotation" ? "annotation" : "viewer";
  } catch {
    return "viewer";
  }
}

interface ModeState {
  mode: AppMode;
  setMode(mode: AppMode): void;
}

export const useModeStore = create<ModeState>((set) => ({
  mode: load(),
  setMode(mode) {
    try {
      localStorage.setItem(KEY, mode);
    } catch {
      // 永続化失敗は無視 (プライベートモード等)
    }
    set({ mode });
  },
}));
