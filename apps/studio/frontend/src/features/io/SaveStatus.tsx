// 自動保存の状態をヘッダ隅へ控えめに出す (Google Docs 風)。トーストではなく常駐テキスト。
// 手動保存 (Cmd/Ctrl+S) のときだけ emphatic で一瞬 ✓ を強調する。
import { useSaveStatusStore } from "../../state/saveStatusStore.ts";
import { useT } from "../../ui/i18n/t.ts";

function hhmm(ms: number): string {
  const d = new Date(ms);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function SaveStatus() {
  const status = useSaveStatusStore((s) => s.status);
  const savedAt = useSaveStatusStore((s) => s.savedAt);
  const emphatic = useSaveStatusStore((s) => s.emphatic);
  const t = useT();

  if (status === "idle") return null;

  let text: string;
  if (status === "saving") text = t("save.saving");
  else if (status === "error") text = t("save.error");
  else if (!savedAt) text = t("save.saved");
  else text = t(emphatic ? "save.savedAt" : "save.autoSavedAt", { time: hhmm(savedAt) });

  return (
    <span
      className={`save-status${emphatic ? " save-status--emphatic" : ""}${status === "error" ? " save-status--error" : ""}`}
      title={t("save.title")}
    >
      {text}
    </span>
  );
}
