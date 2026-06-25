import { THEMES, type ThemeId } from "./theme.ts";

type Props = {
  value: ThemeId;
  onChange: (id: ThemeId) => void;
};

// 画面上部のテーマ選択プルダウン。data-theme を切り替えるだけで
// DOM も Canvas も CSS 変数経由で見た目が変わる。
export function ThemeSwitcher({ value, onChange }: Props) {
  return (
    <label className="theme-switcher">
      <span className="theme-switcher__label">Theme</span>
      <select
        className="select"
        value={value}
        onChange={(e) => onChange(e.target.value as ThemeId)}
      >
        {THEMES.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
    </label>
  );
}
