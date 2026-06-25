import { create } from "zustand";

// 一時的な通知バナー (voxmap.json 読み込み時の draft / 改変検知など)。
export type NoticeKind = "info" | "warn";

interface NoticeState {
  message: string | null;
  kind: NoticeKind;
  notify(message: string, kind?: NoticeKind): void;
  clear(): void;
}

export const useNoticeStore = create<NoticeState>((set) => ({
  message: null,
  kind: "info",
  notify(message, kind = "info") {
    set({ message, kind });
  },
  clear() {
    set({ message: null });
  },
}));
