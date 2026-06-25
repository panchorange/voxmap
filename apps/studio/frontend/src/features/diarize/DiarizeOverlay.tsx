import { useEffect, useState } from "react";
import { estimateDiarizeSec } from "../../domain/estimate.ts";
import { useBackendStore } from "../../state/backendStore.ts";
import { useT } from "../../ui/i18n/t.ts";

// 話者分離は時間がかかるので、波形上に非ブロッキングのグルグル + 経過/推定を出す。
// 推定所要の算出は domain/estimate に切り出し (純粋ロジック)。ここは表示のみ。

type Props = {
  /** 音声長 (秒)。推定所要時間の算出に使う。 */
  durationSec: number;
};

export function DiarizeOverlay({ durationSec }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const device = useBackendStore((s) => s.device);
  const t = useT();

  useEffect(() => {
    const start = performance.now();
    const id = setInterval(() => {
      setElapsed((performance.now() - start) / 1000);
    }, 500);
    return () => clearInterval(id);
  }, []);

  const estimate = estimateDiarizeSec(durationSec, device);

  return (
    <div className="diarize-overlay">
      <div className="spinner" />
      <div className="diarize-overlay__text">
        {t("overlay.diarizing")}
        <span className="faint">
          {t("overlay.progress", { elapsed: elapsed.toFixed(0), estimate })}
        </span>
      </div>
    </div>
  );
}
