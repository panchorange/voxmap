// 分離所要時間の推定 (純粋ロジック)。表示は features/diarize/DiarizeOverlay が行う。
// RTF はデバイス別のざっくり係数。実測 (profiles) より安全側に置く。

/** デバイス別 RTF (実時間 / 音声長)。device 文字列の先頭一致で引く。 */
export const RTF_BY_DEVICE: Record<string, number> = {
  cuda: 0.01,
  mps: 0.03,
  cpu: 0.3,
};

/** device 不明時 (スタブ/未取得) の既定 RTF。 */
export const RTF_FALLBACK = 0.03;

/** 推定所要の下限 (秒)。短い音声でも最低これだけは見せる。 */
export const MIN_ESTIMATE_SEC = 5;

/** device ("cuda:0" | "mps" | "cpu" | null) から RTF を引く。先頭一致 + fallback。 */
export function rtfFor(device: string | null): number {
  if (!device) return RTF_FALLBACK;
  const key = Object.keys(RTF_BY_DEVICE).find((d) => device.startsWith(d));
  return key ? (RTF_BY_DEVICE[key] ?? RTF_FALLBACK) : RTF_FALLBACK;
}

/** 音声長 (秒) と device から分離の推定所要 (秒) を返す。 */
export function estimateDiarizeSec(durationSec: number, device: string | null): number {
  return Math.max(MIN_ESTIMATE_SEC, Math.round(durationSec * rtfFor(device)));
}
