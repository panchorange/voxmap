import { useEditorStore } from "../../state/editorStore.ts";
import { useModeStore } from "../../state/modeStore.ts";
import { useT } from "../../ui/i18n/t.ts";
import { confirmHeardSelection } from "../annotation/confirm.ts";

// 2件以上選択時に出る一括操作バー。
export function BulkBar() {
  const selectedCount = useEditorStore((s) => s.selectedIds.length);
  const speakers = useEditorStore((s) => s.speakers);
  const annotation = useModeStore((s) => s.mode === "annotation");
  const t = useT();

  if (selectedCount < 2) return null;

  return (
    <div className="bulkbar panel">
      <span className="muted" style={{ fontSize: "0.75rem" }}>
        {t("bulk.selectedCount", { n: selectedCount })}
      </span>
      <span className="faint" style={{ fontSize: "0.75rem" }}>
        {t("bulk.assignSpeaker")}
      </span>
      <select
        className="select"
        value=""
        onChange={(e) => {
          if (e.target.value) useEditorStore.getState().pickSpeaker(e.target.value);
        }}
      >
        <option value="" disabled>
          {t("bulk.selectPlaceholder")}
        </option>
        {speakers.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
      {annotation && (
        <button
          type="button"
          className="btn"
          title={t("bulk.confirm.title")}
          onClick={() => {
            const r = confirmHeardSelection();
            if (r.skipped > 0 && r.confirmed === 0) {
              alert(t("bulk.confirm.notHeard"));
            }
          }}
        >
          {t("bulk.confirm")}
        </button>
      )}
      <button
        type="button"
        className="btn btn--danger"
        onClick={() => useEditorStore.getState().deleteSelected()}
      >
        {t("bulk.delete")}
      </button>
      <button
        type="button"
        className="btn"
        style={{ marginLeft: "auto" }}
        onClick={() => useEditorStore.getState().clearSelection()}
      >
        {t("bulk.clear")}
      </button>
    </div>
  );
}
