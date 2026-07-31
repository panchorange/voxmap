// 再生速度の段階定義とステップ計算 (Shift+> / Shift+< で切替)。
// HTMLMediaElement に依存しない純ロジックとして切り出し、単体テスト可能にする。

/** 再生速度の段 (倍)。0.25〜1.5 の 0.25 刻み。 */
export const PLAYBACK_RATES: readonly number[] = [0.25, 0.5, 0.75, 1, 1.25, 1.5];

/** 既定の再生速度 (等速)。 */
export const DEFAULT_RATE = 1;

/**
 * 現在速度を1段上げ下げした値を返す。両端 (0.25 / 1.5) でクランプ。
 * dir=+1 で速く、-1 で遅く。現在値が段に一致しない場合は最近傍の段を基準にする
 * (外部で playbackRate が書き換わっていても破綻しない)。
 */
export function nextPlaybackRate(current: number, dir: 1 | -1): number {
  let idx = 0;
  let bestDiff = Number.POSITIVE_INFINITY;
  PLAYBACK_RATES.forEach((r, i) => {
    const d = Math.abs(r - current);
    if (d < bestDiff) {
      bestDiff = d;
      idx = i;
    }
  });
  idx = Math.min(PLAYBACK_RATES.length - 1, Math.max(0, idx + dir));
  return PLAYBACK_RATES[idx] ?? DEFAULT_RATE;
}

/** 再生速度の下限・上限 (倍)。直接入力のクランプ・段階ボタンの無効化判定で共用する。 */
export const RATE_MIN = PLAYBACK_RATES[0] ?? DEFAULT_RATE;
export const RATE_MAX = PLAYBACK_RATES[PLAYBACK_RATES.length - 1] ?? DEFAULT_RATE;

/**
 * 任意の値を再生速度として使える範囲にクランプする (直接入力用)。
 * 段階 (PLAYBACK_RATES) には縛られず、1.15 / 1.20 のような細かい値もそのまま通す。
 * 数値化できない入力は既定速度にフォールバックする。
 */
export function clampRate(value: number): number {
  if (Number.isNaN(value)) return DEFAULT_RATE;
  return Math.min(RATE_MAX, Math.max(RATE_MIN, value));
}
