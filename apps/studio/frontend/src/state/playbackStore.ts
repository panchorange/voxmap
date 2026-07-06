import { create } from "zustand";
import { DEFAULT_RATE } from "../domain/playback.ts";

// 再生ヘッド位置 / 再生状態 / 再生速度を保持。実制御は PlaybackController (infra)。
interface PlaybackState {
  currentTime: number;
  playing: boolean;
  /** 再生速度 (倍)。UI 表示用のミラー。実体は PlaybackController が持つ。 */
  rate: number;
  setCurrentTime(t: number): void;
  setPlaying(playing: boolean): void;
  setRate(rate: number): void;
}

export const usePlaybackStore = create<PlaybackState>((set) => ({
  currentTime: 0,
  playing: false,
  rate: DEFAULT_RATE,
  setCurrentTime(currentTime) {
    set({ currentTime });
  },
  setPlaying(playing) {
    set({ playing });
  },
  setRate(rate) {
    set({ rate });
  },
}));
