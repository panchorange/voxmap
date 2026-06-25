// 時刻整形の共通ユーティリティ。

/** 秒を mm:ss(.s) に整形。 */
export function fmtTime(t: number, withTenths = false): string {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  const base = `${m}:${s.toString().padStart(2, "0")}`;
  if (!withTenths) return base;
  const tenth = Math.floor((t % 1) * 10);
  return `${base}.${tenth}`;
}

/** 長さ (秒) を 0.00s 形式に。 */
export function fmtDur(sec: number): string {
  return `${sec.toFixed(2)}s`;
}
