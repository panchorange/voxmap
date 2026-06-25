// 確認 (confirm) アクション。アノテーションモードの品質保証として「聴いた区間しか
// 確認できない」を強制する。聴いていない区間は再生して、聴いてから再度確認させる。
import { container } from "../../app/container.ts";
import { useCoverageStore } from "../../state/coverageStore.ts";
import { useEditorStore } from "../../state/editorStore.ts";

/** その区間が再生済みか。 */
export function isHeard(id: string): boolean {
  const ed = useEditorStore.getState();
  const seg = ed.segments.find((s) => s.id === id);
  if (!seg) return false;
  return useCoverageStore.getState().heardSpan(seg.start, seg.end);
}

/**
 * 選択中のうち「聴いた」区間だけを confirmed にする。
 * 1件も聴いていない場合は最初の区間を再生して確認を促す。
 * @returns confirmed = 確認した件数, skipped = 未聴でスキップした件数, played = 再生したか
 */
export function confirmHeardSelection(): { confirmed: number; skipped: number; played: boolean } {
  const ed = useEditorStore.getState();
  const cov = useCoverageStore.getState();
  const sel = ed.segments.filter((s) => ed.selectedIds.includes(s.id));
  if (sel.length === 0) return { confirmed: 0, skipped: 0, played: false };

  const heard = sel.filter((s) => cov.heardSpan(s.start, s.end));
  const unheard = sel.filter((s) => !cov.heardSpan(s.start, s.end));

  if (heard.length > 0) {
    ed.confirmIds(heard.map((s) => s.id));
  } else {
    // 1件も聴いていない → 先頭を再生して「聴く」を促す。
    const first = unheard[0];
    if (first) container.playback.playRegion(first.start, first.end);
  }
  return {
    confirmed: heard.length,
    skipped: unheard.length,
    played: heard.length === 0 && unheard.length > 0,
  };
}
