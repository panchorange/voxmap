import { useEffect, useState } from "react";
import {
  applyTheme,
  type CanvasPalette,
  getStoredTheme,
  readCanvasPalette,
  THEME_CHANGE_EVENT,
  type ThemeId,
} from "./theme.ts";

// 現在のテーマ id と setter。プルダウンから使う。
export function useTheme(): [ThemeId, (id: ThemeId) => void] {
  const [theme, setThemeState] = useState<ThemeId>(getStoredTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return [theme, setThemeState];
}

// Canvas 描画用の色スナップショット。テーマ変更時に再解決される。
export function useCanvasPalette(speakerCount = 10): CanvasPalette {
  const [palette, setPalette] = useState<CanvasPalette>(() => readCanvasPalette(speakerCount));

  useEffect(() => {
    const refresh = () => setPalette(readCanvasPalette(speakerCount));
    window.addEventListener(THEME_CHANGE_EVENT, refresh);
    return () => window.removeEventListener(THEME_CHANGE_EVENT, refresh);
  }, [speakerCount]);

  return palette;
}
