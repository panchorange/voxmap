// autosave の配線。アプリ起動時に1回だけ呼ぶ (main.tsx)。
// 二段構え (ゲームのオートセーブに倣う):
//   1. debounce — 編集の手が止まって DEBOUNCE_MS 経つと保存 (Google Docs / VS Code afterDelay 方式)。
//   2. 定期 — PERIODIC_MS ごとに dirty なら保存 (連続編集中でも取りこぼさない保険)。
// 加えて Cmd/Ctrl+S で即時手動保存 (保存できたことを非侵襲に表示)。
// 保存先は IndexedDB (draftStore)。正式バックアップは「途中保存」(ファイル) が担う裏方。

import { sidecarText } from "../features/io/sidecarSnapshot.ts";
import { saveDraft } from "../infrastructure/draftStore.ts";
import { useAudioStore } from "../state/audioStore.ts";
import { useCatchStore } from "../state/catchStore.ts";
import { useCoverageStore } from "../state/coverageStore.ts";
import { useEditOpsStore } from "../state/editOpsStore.ts";
import { useEditorStore } from "../state/editorStore.ts";
import { useSaveStatusStore } from "../state/saveStatusStore.ts";

/** 編集が止まってから保存するまでの待ち (ms)。 */
export const DEBOUNCE_MS = 2500;
/** 定期保存の間隔 (ms)。連続編集中の保険。 */
export const PERIODIC_MS = 20000;

let wired = false;
let dirty = false;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

/** 現在の編集状態を IndexedDB へ保存する。fileId / segments が無ければ何もしない。 */
async function flush(manual: boolean): Promise<void> {
  const ed = useEditorStore.getState();
  if (!ed.fileId || ed.segments.length === 0) return;
  dirty = false; // 保存対象を確定したら先に下ろす (保存中の編集は次回に拾う)
  useSaveStatusStore.getState().markSaving();
  const { name: audioName, handle: audioHandle } = useAudioStore.getState();
  try {
    await saveDraft({
      fileId: ed.fileId,
      ...(audioName ? { audioName } : {}),
      ...(audioHandle ? { audioHandle } : {}),
      sidecar: sidecarText(ed.segments),
      savedAt: Date.now(),
    });
    useSaveStatusStore.getState().markSaved(Date.now(), manual);
  } catch {
    dirty = true; // 失敗したら dirty を戻し、次の機会に再挑戦
    useSaveStatusStore.getState().markError();
  }
}

/** 編集を検知したら dirty を立て、debounce 保存を仕込む。 */
function markDirty(): void {
  dirty = true;
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    if (dirty) void flush(false);
  }, DEBOUNCE_MS);
}

export function wireAutosave(): void {
  if (wired) return; // 冪等 (StrictMode の二重実行・HMR 対策)
  wired = true;

  // 編集に関わる store の変化で dirty を立てる。autosave は現在状態だけ保存するので、
  // どの経路の編集 (segment / 操作カウンタ / 確認 / 聴取) も拾えるよう全部を購読する。
  useEditorStore.subscribe(markDirty);
  useEditOpsStore.subscribe(markDirty);
  useCatchStore.subscribe(markDirty);
  useCoverageStore.subscribe(markDirty);

  // 定期保存 (保険)。dirty のときだけ書く。
  setInterval(() => {
    if (dirty) void flush(false);
  }, PERIODIC_MS);

  // Cmd/Ctrl+S で即時手動保存。ブラウザの保存ダイアログは抑止する。
  window.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      void flush(true);
    }
  });
}
