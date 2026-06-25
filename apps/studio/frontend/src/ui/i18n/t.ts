// 翻訳関数。文言は messages.ts の単一ソースから引く。
// - useT()    : コンポーネント用。言語変更で自動再レンダされる translator を返す。
// - t()       : React 外 (loadFiles.ts 等) 用。現在言語で 1 回翻訳する。
// - translate(): 言語を明示して翻訳する低レベル関数 (上の 2 つが内部で使う)。
import { useLangStore } from "./langStore.ts";
import { type Lang, MESSAGES, type MessageKey } from "./messages.ts";

type Vars = Record<string, string | number>;

export function translate(lang: Lang, key: MessageKey, vars?: Vars): string {
  let s: string = MESSAGES[key][lang];
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{${k}}`, String(v));
    }
  }
  return s;
}

// React 外から現在言語で翻訳する (通知メッセージ等)。再レンダ追従はしない。
export function t(key: MessageKey, vars?: Vars): string {
  return translate(useLangStore.getState().lang, key, vars);
}

// コンポーネント用。言語を購読し、変更時に再レンダされる translator を返す。
export function useT(): (key: MessageKey, vars?: Vars) => string {
  const lang = useLangStore((s) => s.lang);
  return (key, vars) => translate(lang, key, vars);
}
