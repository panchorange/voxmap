// 自動分離の実行。container.diarization (今は Stub、将来 httpDiarization) を呼び、
// 返ってきた Segment[] を取り込む。アダプタ差し替えだけで本番接続できる。
// annotation モードのときだけ最大 3 個のキャッチトライアル (phantom) を仕込む。
import { container } from "../../app/container.ts";
import { catchCount, injectPhantoms } from "../../domain/catch.ts";
import { deriveSpeakerOrder } from "../../domain/speaker.ts";
import type { ClusterMapping } from "../../domain/types.ts";
import { useAudioStore } from "../../state/audioStore.ts";
import { useCatchStore } from "../../state/catchStore.ts";
import { newId, useEditorStore } from "../../state/editorStore.ts";
import { useModeStore } from "../../state/modeStore.ts";
import { enableFollowEdits } from "../recommend/followEdits.ts";

/** 分離後に一括対応ポップアップへ渡す情報。区間は store に取り込み済み。 */
export interface DiarizeOutcome {
  clusterMapping: ClusterMapping[];
  galleryNames: string[];
}

/** numSpeakers: 話者数を固定 (null = AUTO で推定)。 */
export async function runDiarization(numSpeakers: number | null = null): Promise<DiarizeOutcome> {
  const audioState = useAudioStore.getState();
  const file = audioState.file;
  if (!file) return { clusterMapping: [], galleryNames: [] };
  const result = await container.diarization.diarize(file, numSpeakers);

  const catchEnabled = useModeStore.getState().mode === "annotation";
  const duration = audioState.audio?.duration ?? 0;
  if (catchEnabled && duration > 0) {
    const { segments, trials } = injectPhantoms(
      result.segments,
      duration,
      catchCount(duration),
      deriveSpeakerOrder(result.segments),
      newId,
    );
    useCatchStore.getState().setTrials(trials);
    useEditorStore.getState().importSegments(segments, useEditorStore.getState().fileId);
  } else {
    useCatchStore.getState().clear();
    useEditorStore.getState().importSegments(result.segments, useEditorStore.getState().fileId);
  }
  // 以降の編集で怪しさ/レコメンドを追従させる (backend グリッド保持済み)。
  enableFollowEdits();
  return { clusterMapping: result.clusterMapping, galleryNames: result.galleryNames };
}
