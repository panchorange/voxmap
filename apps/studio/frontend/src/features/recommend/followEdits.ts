// 編集追従: segment の移動/幅変更/分割などで怪しさ・レコメンドを再計算する。
// backend が保持する埋め込みグリッドを使うので再埋め込みは不要 (分離後のみ有効)。
//
// ループ防止: geometry (id/start/end/speaker) のシグネチャが変わったときだけ recompute する。
// applySignals は suspicion/recommendation しか変えない → シグネチャ不変 → 再発火しない。

import { container } from "../../app/container.ts";
import type { Segment } from "../../domain/types.ts";
import { useEditorStore } from "../../state/editorStore.ts";
import { useModeStore } from "../../state/modeStore.ts";

const DEBOUNCE_MS = 500;

let enabled = false;
let timer: ReturnType<typeof setTimeout> | null = null;
let lastSig = "";

function geometrySignature(segs: Segment[]): string {
  return segs
    .map((s) => `${s.id}:${s.start.toFixed(3)}:${s.end.toFixed(3)}:${s.speaker}`)
    .join("|");
}

async function runRecompute(): Promise<void> {
  const segs = useEditorStore.getState().segments;
  try {
    const patches = await container.diarization.recompute(
      segs.map((s) => ({ id: s.id, start: s.start, end: s.end, speaker: s.speaker })),
    );
    useEditorStore.getState().applySignals(patches);
  } catch {
    // 追従は best-effort。失敗しても既存の表示を保つ (致命的でない)。
  }
}

/** 分離完了後に呼ぶ。以降の geometry 編集で怪しさ/レコメンドを追従させる。 */
export function enableFollowEdits(): void {
  enabled = true;
  lastSig = geometrySignature(useEditorStore.getState().segments);
  if (timer) clearTimeout(timer); // import 時に貼られた予約を取り消す (新分離は再計算不要)
}

/** 起動時に1回。segments の geometry 変化を debounce して recompute する。 */
export function wireFollowEdits(): void {
  useEditorStore.subscribe((s) => {
    if (!enabled || useModeStore.getState().mode !== "annotation") return;
    const sig = geometrySignature(s.segments);
    if (sig === lastSig) return; // geometry 不変 (applySignals/選択変更 等) → 何もしない
    lastSig = sig;
    if (timer) clearTimeout(timer);
    timer = setTimeout(runRecompute, DEBOUNCE_MS);
  });
}
