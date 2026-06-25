import { create } from "zustand";

// 候補パネル (R) の開閉。対象は「現在のセグメント」1 つ (フォーカスモデル §6.2)。
interface RecommendState {
  /** パネルを開いているセグメント id。null = 閉じている。 */
  openId: string | null;
  open(id: string): void;
  close(): void;
}

export const useRecommendStore = create<RecommendState>((set) => ({
  openId: null,
  open: (id) => set({ openId: id }),
  close: () => set({ openId: null }),
}));
