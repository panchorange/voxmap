import { create } from "zustand";

// backend の実行情報。起動時に /api/health から 1 回取得してキャッシュする。
// device は分離の所要時間の見積もり (DiarizeOverlay) に使う。
interface BackendState {
  /** 解決済みデバイス ("cuda:0" | "mps" | "cpu")。未取得/スタブ時は null。 */
  device: string | null;
  fetchHealth(): Promise<void>;
}

export const useBackendStore = create<BackendState>((set) => ({
  device: null,
  async fetchHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) return;
      const data = (await res.json()) as { device?: string };
      set({ device: data.device ?? null });
    } catch {
      // スタブ/未起動時は取得失敗 → null のまま (見積もりは既定値)。
    }
  },
}));
