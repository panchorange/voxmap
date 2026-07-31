// テーマの定義と適用。CSS 変数 (themes.css) を単一ソースとし、
// DOM は class 経由、Canvas は readCanvasPalette() でこの変数を読む。

export const THEMES = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
  { id: "ocean", label: "Ocean" },
  { id: "famicom", label: "Famicom" },
  { id: "brown", label: "Brown" },
  { id: "nord", label: "Nord" },
  { id: "gameboy", label: "Game Boy" },
  { id: "yusha", label: "Yusha" },
  { id: "yozakura", label: "Yozakura" },
  { id: "blackdiamond", label: "Black Diamond" },
  { id: "yell", label: "Yell" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

/**
 * プルダウンに出さないテーマ。**実装 (CSS ブロック) は残す**ので、保存済み設定や
 * 手動で data-theme を差し替えた場合は引き続き有効。棚から下げるだけの一覧。
 */
const HIDDEN_THEMES: readonly ThemeId[] = ["gameboy", "brown", "blackdiamond"];

/** プルダウンに並べるテーマ。THEMES から HIDDEN_THEMES を除いたもの。 */
export const VISIBLE_THEMES = THEMES.filter((t) => !HIDDEN_THEMES.includes(t.id));

export function isHiddenTheme(id: ThemeId): boolean {
  return HIDDEN_THEMES.includes(id);
}

const STORAGE_KEY = "voxmap-studio.theme";
const DEFAULT_THEME: ThemeId = "dark";
// data-theme が変わったことを Canvas 側へ知らせるためのイベント名。
export const THEME_CHANGE_EVENT = "voxmap-studio:theme-change";

function isThemeId(value: string | null): value is ThemeId {
  return THEMES.some((t) => t.id === value);
}

export function getStoredTheme(): ThemeId {
  const stored = localStorage.getItem(STORAGE_KEY);
  return isThemeId(stored) ? stored : DEFAULT_THEME;
}

export function applyTheme(id: ThemeId): void {
  document.documentElement.setAttribute("data-theme", id);
  localStorage.setItem(STORAGE_KEY, id);
  window.dispatchEvent(new CustomEvent(THEME_CHANGE_EVENT, { detail: id }));
}

// Canvas が読む色トークン。CSS 変数名 -> パレットのキー。
const CANVAS_VARS = {
  waveBg: "--wave-bg",
  rulerBg: "--wave-ruler-bg",
  grid: "--wave-grid",
  midline: "--wave-midline",
  rulerText: "--wave-ruler-text",
  segDefault: "--seg-default",
  segNoSpeaker: "--seg-no-speaker",
  segSelected: "--seg-selected",
  playhead: "--playhead",
  suspicionIntruder: "--suspicion-intruder",
  suspicionBoundary: "--suspicion-boundary",
} as const;

export type CanvasPalette = Record<keyof typeof CANVAS_VARS, string> & {
  speakers: string[];
};

// 現在の data-theme の CSS 変数を解決してスナップショットを返す。
// getComputedStyle は重いので毎フレームではなくテーマ変更時にだけ呼ぶこと。
export function readCanvasPalette(speakerCount = 10): CanvasPalette {
  const cs = getComputedStyle(document.documentElement);
  const get = (v: string) => cs.getPropertyValue(v).trim();

  const palette = {} as CanvasPalette;
  for (const [key, cssVar] of Object.entries(CANVAS_VARS)) {
    palette[key as keyof typeof CANVAS_VARS] = get(cssVar);
  }
  palette.speakers = Array.from({ length: speakerCount }, (_, i) => get(`--spk-${i}`));
  return palette;
}
