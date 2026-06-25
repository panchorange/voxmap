import { create } from "zustand";

// Phase 1 では再生ヘッド位置の保持のみ。実際の再生制御は Phase 5。
interface PlaybackState {
  currentTime: number;
  playing: boolean;
  setCurrentTime(t: number): void;
  setPlaying(playing: boolean): void;
}

export const usePlaybackStore = create<PlaybackState>((set) => ({
  currentTime: 0,
  playing: false,
  setCurrentTime(currentTime) {
    set({ currentTime });
  },
  setPlaying(playing) {
    set({ playing });
  },
}));
