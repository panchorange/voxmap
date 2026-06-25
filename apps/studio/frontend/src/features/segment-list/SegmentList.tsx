import { useRef } from "react";
import { container } from "../../app/container.ts";
import { speakerColor } from "../../domain/speaker.ts";
import type { SegmentStatus } from "../../domain/types.ts";
import { useCoverageStore } from "../../state/coverageStore.ts";
import { useEditorStore } from "../../state/editorStore.ts";
import { useModeStore } from "../../state/modeStore.ts";
import { fmtDur, fmtTime } from "../../ui/format.ts";
import type { MessageKey } from "../../ui/i18n/messages.ts";
import { useT } from "../../ui/i18n/t.ts";
import { useCanvasPalette } from "../../ui/theme/useTheme.ts";

const STATUS_LABEL_KEY: Record<SegmentStatus, MessageKey> = {
  auto: "seglist.status.auto",
  edited: "seglist.status.edited",
  confirmed: "seglist.status.confirmed",
};

// 区間リスト。start 昇順。行クリックで選択+ジャンプ、修飾キーでトグル/範囲。
export function SegmentList() {
  const segments = useEditorStore((s) => s.segments);
  const selectedIds = useEditorStore((s) => s.selectedIds);
  const speakers = useEditorStore((s) => s.speakers);
  const annotation = useModeStore((s) => s.mode === "annotation");
  const palette = useCanvasPalette();
  const t = useT();
  const lastIndex = useRef(0);

  const sorted = [...segments].sort((a, b) => a.start - b.start);
  const selected = new Set(selectedIds);

  const onRowClick = (e: React.MouseEvent, id: string, index: number, start: number) => {
    const ed = useEditorStore.getState();
    if (e.metaKey || e.ctrlKey) {
      ed.toggleSelect(id);
    } else if (e.shiftKey) {
      const [lo, hi] = [Math.min(lastIndex.current, index), Math.max(lastIndex.current, index)];
      ed.setSelection(sorted.slice(lo, hi + 1).map((s) => s.id));
    } else {
      ed.selectSingle(id);
      container.playback.seek(start);
      lastIndex.current = index;
    }
  };

  if (!sorted.length) {
    return (
      <p className="faint" style={{ fontSize: "0.75rem" }}>
        {t("seglist.empty")}
      </p>
    );
  }

  return (
    <div className="seglist">
      {sorted.map((s, i) => (
        // biome-ignore lint/a11y/noStaticElementInteractions: 区間行の選択操作
        // biome-ignore lint/a11y/useKeyWithClickEvents: キーボードは useKeyboard が担当
        <div
          key={s.id}
          className={`seglist__row${selected.has(s.id) ? " seglist__row--sel" : ""}`}
          onClick={(e) => onRowClick(e, s.id, i, s.start)}
          onDoubleClick={() => container.playback.playRegion(s.start, s.end)}
        >
          <span className="seglist__idx faint">{i + 1}</span>
          <span className="seglist__time">
            {fmtTime(s.start, true)} → {fmtTime(s.end, true)}
          </span>
          <span className="seglist__dur faint">{fmtDur(s.end - s.start)}</span>
          {annotation && (
            <button
              type="button"
              className={`seglist__status seglist__status--${s.status}`}
              title={t(
                s.status === "confirmed"
                  ? "seglist.status.confirmedTitle"
                  : "seglist.status.confirmTitle",
              )}
              onClick={(e) => {
                e.stopPropagation();
                if (s.status === "confirmed") return;
                if (useCoverageStore.getState().heardSpan(s.start, s.end)) {
                  useEditorStore.getState().confirmIds([s.id]);
                } else {
                  container.playback.playRegion(s.start, s.end);
                }
              }}
            >
              {t(STATUS_LABEL_KEY[s.status])}
            </button>
          )}
          <span
            className="chip__dot"
            style={{ background: speakerColor(s.speaker, speakers, palette.speakers) }}
          />
          <select
            className="select"
            value={s.speaker}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => useEditorStore.getState().setSegmentSpeaker(s.id, e.target.value)}
          >
            {speakers.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn--danger"
            onClick={(e) => {
              e.stopPropagation();
              useEditorStore.getState().deleteSegment(s.id);
            }}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
