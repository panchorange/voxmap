// 現在の編集状態を voxmap.json (sidecar) 文字列へ直列化する共有ロジック。
// 「途中保存」(手動ファイル書き出し)・「完成書き出し」・autosave のいずれもここを通る。
import { evaluateCatch } from "../../domain/catch.ts";
import { type SidecarInput, serializeSidecar } from "../../domain/sidecar.ts";
import { useAudioStore } from "../../state/audioStore.ts";
import { useCatchStore } from "../../state/catchStore.ts";
import { useCoverageStore } from "../../state/coverageStore.ts";
import { useEditOpsStore } from "../../state/editOpsStore.ts";
import { useEditorStore } from "../../state/editorStore.ts";
import { useSessionStore } from "../../state/sessionStore.ts";

/** 渡した segments で sidecar 文字列を作る。完成書き出しは phantom 除去後の segments を渡す。 */
export function sidecarText(segments: SidecarInput["segments"]): string {
  const ed = useEditorStore.getState();
  const session = useSessionStore.getState();
  const ops = useEditOpsStore.getState();
  const now = performance.now();
  return serializeSidecar({
    fileId: ed.fileId,
    ...(useAudioStore.getState().name
      ? { audioName: useAudioStore.getState().name as string }
      : {}),
    mode: "annotation",
    segments,
    percentHeard: useCoverageStore.getState().percentHeard(),
    catch: evaluateCatch(useCatchStore.getState().trials, ed.segments),
    exportedAt: new Date().toISOString(),
    // 初回開始時刻。再開を重ねても保たれ、exportedAt との差で日跨ぎ込みの総スパンになる。
    ...(session.createdAt ? { createdAt: session.createdAt } : {}),
    // 作業コスト計測 (§4): 途中保存・完成版どちらの JSON にも入る。
    cost: {
      activeSec: session.activeSec,
      wallSec: session.wallSec(now),
      audioSec: useCoverageStore.getState().duration,
      editOps: ops.total(),
      editOpsDetail: {
        reassign: ops.reassign,
        resize: ops.resize,
        split: ops.split,
        create: ops.create,
        del: ops.del,
      },
    },
  });
}
