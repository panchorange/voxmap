import { useState } from "react";
import { speakerColor } from "../../domain/speaker.ts";
import { useEditorStore } from "../../state/editorStore.ts";
import { useT } from "../../ui/i18n/t.ts";
import { useCanvasPalette } from "../../ui/theme/useTheme.ts";

// 話者チップ。クリックで activeSpeaker 設定 + (選択があれば) 一括割当。
// ダブルクリックでラベルをインライン編集 (リネーム)。
export function SpeakerChips() {
  const speakers = useEditorStore((s) => s.speakers);
  const segments = useEditorStore((s) => s.segments);
  const activeSpeaker = useEditorStore((s) => s.activeSpeaker);
  const palette = useCanvasPalette();
  const t = useT();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startEdit = (name: string) => {
    setEditing(name);
    setDraft(name);
  };
  const commit = () => {
    if (editing) useEditorStore.getState().renameSpeaker(editing, draft);
    setEditing(null);
  };
  const remove = (name: string) => {
    const count = segments.filter((s) => s.speaker === name).length;
    if (count > 0 && !confirm(t("chips.removeConfirm", { name, count }))) return;
    useEditorStore.getState().removeSpeaker(name);
  };

  return (
    <div className="chips">
      {speakers.map((name) => {
        const color = speakerColor(name, speakers, palette.speakers);
        const active = name === activeSpeaker;
        if (editing === name) {
          return (
            <input
              key={name}
              type="text"
              className="chip__input"
              style={{ borderColor: color }}
              value={draft}
              ref={(el) => el?.focus()}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => {
                if (e.key === "Enter") commit();
                else if (e.key === "Escape") setEditing(null);
              }}
            />
          );
        }
        return (
          <span
            key={name}
            className={`chip${active ? " chip--active" : ""}`}
            style={{ borderColor: color }}
          >
            <button
              type="button"
              className="chip__label"
              title={t("chips.label.title")}
              onClick={() => useEditorStore.getState().pickSpeaker(name)}
              onDoubleClick={() => startEdit(name)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  startEdit(name);
                }
              }}
            >
              <span className="chip__dot" style={{ background: color }} />
              {name}
            </button>
            <button
              type="button"
              className="chip__x"
              title={t("chips.remove.title", { name })}
              onClick={() => remove(name)}
            >
              ×
            </button>
          </span>
        );
      })}
      <button type="button" className="btn" onClick={() => useEditorStore.getState().addSpeaker()}>
        {t("chips.add")}
      </button>
    </div>
  );
}
