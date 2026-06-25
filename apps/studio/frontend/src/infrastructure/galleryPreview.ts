// 既知話者 (ギャラリ) の代表クリップを試聴する。メインの音声再生 (PlaybackController)
// とは別の専用 Audio 要素を使い、読み込み中の会議音声を邪魔しない。
let el: HTMLAudioElement | null = null;

/** `name` (例 "EN2002a/MEE073") の代表クリップを backend から取得して再生する。 */
export function playGalleryClip(name: string, baseUrl = "/api"): void {
  if (!el) el = new Audio();
  el.src = `${baseUrl}/gallery/preview?name=${encodeURIComponent(name)}`;
  el.currentTime = 0;
  void el.play().catch(() => {}); // クリップ無し (404) 等は無視
}
