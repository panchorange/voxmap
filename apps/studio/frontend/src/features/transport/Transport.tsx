import { useRef, useState } from "react";
import { container } from "../../app/container.ts";
import { clampRate, RATE_MAX, RATE_MIN } from "../../domain/playback.ts";
import { useAudioStore } from "../../state/audioStore.ts";
import { usePlaybackStore } from "../../state/playbackStore.ts";
import { fmtTime } from "../../ui/format.ts";

// 再生コントロール。再生/停止 + 時刻表示 + 再生速度 (Shift+>/< と同期)。
export function Transport() {
  const playing = usePlaybackStore((s) => s.playing);
  const currentTime = usePlaybackStore((s) => s.currentTime);
  const rate = usePlaybackStore((s) => s.rate);
  const audio = useAudioStore((s) => s.audio);
  const duration = audio?.duration ?? 0;
  const [editingRate, setEditingRate] = useState(false);
  const [rateDraft, setRateDraft] = useState("");
  // Escapeでキャンセルした直後、フォーカスが外れたinputの native blur が
  // React の onBlur(commitRate) を発火させドラフトを確定させてしまうことがある
  // (制御されたinputをフォーカスしたまま unmount した際の既知の挙動)。
  // このフラグでキャンセル直後の1回だけ commitRate を無効化する。
  const cancelledRef = useRef(false);

  const startEditRate = () => {
    if (!audio) return;
    setRateDraft(String(rate));
    setEditingRate(true);
  };
  const commitRate = () => {
    if (cancelledRef.current) {
      cancelledRef.current = false;
      return;
    }
    const parsed = Number.parseFloat(rateDraft);
    container.playback.setRate(clampRate(parsed));
    setEditingRate(false);
  };
  const cancelEditRate = () => {
    cancelledRef.current = true;
    setEditingRate(false);
  };

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
        {editingRate ? (
          <input
            type="number"
            className="transport__rate-input"
            step="0.01"
            min={RATE_MIN}
            max={RATE_MAX}
            value={rateDraft}
            autoFocus
            aria-label="再生速度を直接入力"
            onChange={(e) => setRateDraft(e.target.value)}
            onBlur={commitRate}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRate();
              else if (e.key === "Escape") cancelEditRate();
            }}
          />
        ) : (
          <button
            type="button"
            className="transport__rate"
            disabled={!audio}
            title="クリックで直接入力 (Shift+> / Shift+< で段階変更)"
            onClick={startEditRate}
          >
            {rate}×
          </button>
        )}
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
