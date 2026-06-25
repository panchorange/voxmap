import { container } from "../../app/container.ts";
import { useAudioStore } from "../../state/audioStore.ts";
import { usePlaybackStore } from "../../state/playbackStore.ts";
import { fmtTime } from "../../ui/format.ts";

// 再生コントロール。再生/停止 + 時刻表示。
export function Transport() {
  const playing = usePlaybackStore((s) => s.playing);
  const currentTime = usePlaybackStore((s) => s.currentTime);
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
    </div>
  );
}
