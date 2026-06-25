// 画面上部の JP/EN 切替トグル。ThemeSwitcher の隣に並べる。
// 押すと langStore が <html lang> と localStorage を更新し、useT を使う
// コンポーネントが再レンダされて文言が切り替わる。
import { useLangStore } from "./langStore.ts";
import { LANGS } from "./messages.ts";

export function LangSwitcher() {
  const lang = useLangStore((s) => s.lang);
  const setLang = useLangStore((s) => s.setLang);

  return (
    <div className="lang-switcher">
      {LANGS.map((l) => (
        <button
          key={l.id}
          type="button"
          className={`lang-switcher__btn${lang === l.id ? " lang-switcher__btn--active" : ""}`}
          aria-pressed={lang === l.id}
          onClick={() => setLang(l.id)}
        >
          {l.id.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
