import { isHiddenTheme, THEMES, type ThemeId, VISIBLE_THEMES } from "./theme.ts";

type Props = {
  value: ThemeId;
  onChange: (id: ThemeId) => void;
};

// 画面上部のテーマ選択プルダウン。data-theme を切り替えるだけで
// DOM も Canvas も CSS 変数経由で見た目が変わる。
export function ThemeSwitcher({ value, onChange }: Props) {
  // 非表示テーマを選んだ状態で残っている人は select が空欄になってしまうので、
  // 現在値だけは例外的に並べる (別のテーマに切り替えた時点で一覧から消える)。
  const options = isHiddenTheme(value)
    ? [...VISIBLE_THEMES, ...THEMES.filter((t) => t.id === value)]
    : VISIBLE_THEMES;
  return (
    <label className="theme-switcher">
      <span className="theme-switcher__label">Theme</span>
      <select
        className="select"
        value={value}
        onChange={(e) => onChange(e.target.value as ThemeId)}
      >
        {options.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
    </label>
  );
}
