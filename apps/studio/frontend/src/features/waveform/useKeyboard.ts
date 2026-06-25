import { useEffect } from "react";
import { useEditorStore } from "../../state/editorStore.ts";
import { useModeStore } from "../../state/modeStore.ts";
import { usePlaybackStore } from "../../state/playbackStore.ts";
import { useRecommendStore } from "../../state/recommendStore.ts";
import { confirmHeardSelection } from "../annotation/confirm.ts";

// グローバルキー: Delete/Backspace=削除, Esc=解除, Cmd/Ctrl+Z=undo, +Shift=redo,
//   C=確認, S=再生位置で分割, R=候補パネル。入力欄フォーカス中は無視する。
export function useKeyboard(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) {
        return;
      }
      const ed = useEditorStore.getState();

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) ed.redo();
        else ed.undo();
        return;
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        if (ed.selectedIds.length) {
          e.preventDefault();
          ed.deleteSelected();
        }
        return;
      }
      if (e.key === "Escape") {
        // 候補パネルが開いていれば先に閉じる (選択は維持)。
        if (useRecommendStore.getState().openId) useRecommendStore.getState().close();
        else ed.clearSelection();
        return;
      }
      // r: 現在のセグメント (単一選択) の候補パネルを開く (フォーカスモデル §6.2)。
      if (e.key.toLowerCase() === "r" && !e.metaKey && !e.ctrlKey) {
        const id = ed.selectedIds.length === 1 ? ed.selectedIds[0] : null;
        if (id) {
          e.preventDefault();
          useRecommendStore.getState().open(id);
        }
        return;
      }
      // S: 単一選択区間を再生ヘッド位置で分割。
      if (e.key.toLowerCase() === "s" && !e.metaKey && !e.ctrlKey) {
        const id = ed.selectedIds.length === 1 ? ed.selectedIds[0] : null;
        if (id) {
          e.preventDefault();
          ed.splitAt(id, usePlaybackStore.getState().currentTime);
        }
        return;
      }
      // C: 選択中の (聴いた) 区間を確認。annotation モードのみ。
      if (e.key.toLowerCase() === "c" && !e.metaKey && !e.ctrlKey) {
        if (useModeStore.getState().mode === "annotation" && ed.selectedIds.length) {
          e.preventDefault();
          confirmHeardSelection();
        }
        return;
      }
      // 数字キー 1–9: その話者を activeSpeaker にし、選択へ一括割当。
      if (/^[1-9]$/.test(e.key) && !e.metaKey && !e.ctrlKey) {
        const name = ed.speakers[Number(e.key) - 1];
        if (name) {
          e.preventDefault();
          ed.pickSpeaker(name);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
