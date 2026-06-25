import { create } from "zustand";
import type { CatchTrial } from "../domain/catch.ts";

// セッション中に仕込んだキャッチトライアル (phantom)。自動分離 (annotation モード) ごとに
// 入れ替える。新しい音声・RTTM 取込でクリアする。
interface CatchState {
  trials: CatchTrial[];
  setTrials(trials: CatchTrial[]): void;
  clear(): void;
}

export const useCatchStore = create<CatchState>((set) => ({
  trials: [],
  setTrials(trials) {
    set({ trials });
  },
  clear() {
    set({ trials: [] });
  },
}));
