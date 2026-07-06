import { container } from "../../app/container.ts";
import { DEFAULT_RATE, PLAYBACK_RATES } from "../../domain/playback.ts";
import { useAudioStore } from "../../state/audioStore.ts";
import { usePlaybackStore } from "../../state/playbackStore.ts";
import { fmtTime } from "../../ui/format.ts";

const RATE_MIN = PLAYBACK_RATES[0] ?? DEFAULT_RATE;
const RATE_MAX = PLAYBACK_RATES[PLAYBACK_RATES.length - 1] ?? DEFAULT_RATE;

// 再生コントロール。再生/停止 + 時刻表示 + 再生速度 (Shift+>/< と同期)。
export function Transport() {
  const playing = usePlaybackStore((s) => s.playing);
  const currentTime = usePlaybackStore((s) => s.currentTime);
  const rate = usePlaybackStore((s) => s.rate);
  const audio = useAudioStore((s) => s.audio);
  const duration = audio?.duration ?? 0;

  return (
    <div className="transport">
      <button
        type="button"
        className="btn btn--accent transport__play"
        disabled={!audio}
        onClick={() => container.playback.toggle()}
      >
        {playing ? "⏸" : "▶"}
      </button>
      <span className="transport__time">
        {fmtTime(currentTime, true)} <span className="faint">/ {fmtTime(duration, true)}</span>
      </span>
      <div className="transport__speed">
        <button
          type="button"
          className="btn transport__speed-btn"
          disabled={!audio || rate <= RATE_MIN}
          title="遅く (Shift+<)"
          aria-label="再生速度を下げる"
          onClick={() => container.playback.stepRate(-1)}
        >
          ‹
        </button>
        <span className="transport__rate" title="Shift+> / Shift+< で変更">
          {rate}×
        </span>
        <button
          type="button"
          className="btn transport__speed-btn"
          disabled={!audio || rate >= RATE_MAX}
          title="速く (Shift+>)"
          aria-label="再生速度を上げる"
          onClick={() => container.playback.stepRate(1)}
        >
          ›
        </button>
      </div>
    </div>
  );
}
