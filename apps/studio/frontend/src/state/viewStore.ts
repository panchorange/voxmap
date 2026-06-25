import { create } from "zustand";
import {
  clampOffset,
  fit as fitView,
  panBy,
  type View,
  type Viewport,
  zoomAt,
} from "../domain/coords.ts";

interface ViewState extends View {
  /** 最新のビューポート (Canvas のリサイズ/音声ロードで更新)。centerOn 等が参照する。 */
  vp: Viewport;
  /** ビューポートを記録する (fit はしない)。WaveformCanvas が随時更新。 */
  setViewport(viewport: Viewport): void;
  zoomAt(anchorX: number, factor: number, viewport: Viewport): void;
  zoomButton(factor: number, viewport: Viewport): void;
  pan(dxPx: number, viewport: Viewport): void;
  fit(viewport: Viewport): void;
  /** time が表示左端の 10% 付近に来るようスクロール (再生追従用)。 */
  scrollTo(time: number, viewport: Viewport): void;
  /** time を画面内 (左から ~35%) に収めるようスクロール。記録済み vp を使う (引数不要)。 */
  centerOn(time: number): void;
}

export const useViewStore = create<ViewState>((set, get) => ({
  pps: 100,
  offset: 0,
  vp: { widthPx: 0, duration: 0 },
  setViewport(viewport) {
    set({ vp: viewport });
  },
  zoomAt(anchorX, factor, viewport) {
    set(zoomAt(get(), anchorX, factor, viewport));
  },
  zoomButton(factor, viewport) {
    // 画面中央を固定点にズーム。
    set(zoomAt(get(), viewport.widthPx / 2, factor, viewport));
  },
  pan(dxPx, viewport) {
    set(panBy(get(), dxPx, viewport));
  },
  fit(viewport) {
    set(fitView(viewport));
  },
  scrollTo(time, viewport) {
    const v = get();
    const offset = time - (viewport.widthPx * 0.1) / v.pps;
    set({ offset: clampOffset(offset, v, viewport) });
  },
  centerOn(time) {
    const v = get();
    const vp = v.vp;
    if (vp.widthPx <= 0) return;
    const offset = time - (vp.widthPx * 0.35) / v.pps;
    set({ offset: clampOffset(offset, v, vp) });
  },
}));
