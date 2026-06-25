import { type AppMode, useModeStore } from "../../state/modeStore.ts";
import type { MessageKey } from "../../ui/i18n/messages.ts";
import { useT } from "../../ui/i18n/t.ts";

const OPTIONS: { value: AppMode; labelKey: MessageKey }[] = [
  { value: "viewer", labelKey: "mode.viewer" },
  { value: "annotation", labelKey: "mode.annotation" },
];

// アプリモード切替 (ヘッダー右)。annotation のときだけ QA レイヤが有効になる。
export function ModeToggle() {
  const mode = useModeStore((s) => s.mode);
  const setMode = useModeStore((s) => s.setMode);
  const t = useT();

  return (
    <div className="modetoggle">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          className={`modetoggle__btn${mode === o.value ? " modetoggle__btn--active" : ""}`}
          aria-pressed={mode === o.value}
          onClick={() => setMode(o.value)}
        >
          {t(o.labelKey)}
        </button>
      ))}
    </div>
  );
}
