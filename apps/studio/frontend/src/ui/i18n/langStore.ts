// 表示言語の状態 (ja / en)。テーマと同じく localStorage に永続化するが、
// React 外 (loadFiles.ts の notify 等) からも現在言語を読めるよう Zustand store にする。
// <html lang> 属性も同期し、スクリーンリーダ・ブラウザ翻訳のヒントにする。
import { create } from "zustand";
import { isLang, type Lang } from "./messages.ts";

const STORAGE_KEY = "voxmap-studio.lang";

// 初期言語: 保存値 > ブラウザ言語が日本語なら ja > 既定 en。
function getStoredLang(): Lang {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (isLang(stored)) return stored;
  return navigator.language.startsWith("ja") ? "ja" : "en";
}

function applyLangAttr(lang: Lang): void {
  document.documentElement.setAttribute("lang", lang);
}

interface LangState {
  lang: Lang;
  setLang(lang: Lang): void;
}

export const useLangStore = create<LangState>((set) => {
  const initial = getStoredLang();
  applyLangAttr(initial);
  return {
    lang: initial,
    setLang(lang) {
      localStorage.setItem(STORAGE_KEY, lang);
      applyLangAttr(lang);
      set({ lang });
    },
  };
});
