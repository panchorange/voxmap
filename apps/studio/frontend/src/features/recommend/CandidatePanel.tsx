import { container } from "../../app/container.ts";
import { speakerColor } from "../../domain/speaker.ts";
import { useEditorStore } from "../../state/editorStore.ts";
import { useRecommendStore } from "../../state/recommendStore.ts";
import { useViewStore } from "../../state/viewStore.ts";
import { fmtTime } from "../../ui/format.ts";
import { useT } from "../../ui/i18n/t.ts";
import { useCanvasPalette } from "../../ui/theme/useTheme.ts";

const PREVIEW_MAX_SEC = 5;

/** その話者ラインの最長セグメントを最大 5 秒だけ試聴する (声の聴き比べ用)。 */
function previewSpeaker(line: string): void {
  const segs = useEditorStore.getState().segments.filter((s) => s.speaker === line);
  if (!segs.length) return;
  const rep = segs.reduce((a, b) => (b.end - b.start > a.end - a.start ? b : a));
  container.playback.playRegion(rep.start, Math.min(rep.end, rep.start + PREVIEW_MAX_SEC));
}

/**
 * 候補話者パネル (§6.3)。現在のセグメントに対し、現在の話者ラインへの cos を降順表示。
 * 候補クリックで、移動元と異なれば その話者ラインへ付け替える。各候補に試聴ボタン。
 */
export function CandidatePanel() {
  const openId = useRecommendStore((s) => s.openId);
  const close = useRecommendStore((s) => s.close);
  const seg = useEditorStore((s) => s.segments.find((x) => x.id === openId) ?? null);
  const speakers = useEditorStore((s) => s.speakers);
  const palette = useCanvasPalette();
  const t = useT();

  if (!openId || !seg) return null;
  const rec = seg.recommendation;

  // 試聴で視点が候補話者の位置へ移動しているため、付け替え後に編集セグメントへ
  // 視点を戻す。これでライン移動 (別レーンへ飛ぶ様子) が画面内で見える。
  const recenter = () => useViewStore.getState().centerOn(seg.start);

  const moveTo = (line: string) => {
    if (line !== seg.speaker) {
      useEditorStore.getState().setSegmentSpeaker(seg.id, line);
      recenter();
    }
    close();
  };
  const moveToNew = () => {
    const ed = useEditorStore.getState();
    ed.addSpeaker();
    const created = ed.activeSpeaker; // addSpeaker が activeSpeaker に新ラインを設定する
    if (created) ed.setSegmentSpeaker(seg.id, created);
    recenter();
    close();
  };

  return (
    <div className="candidate">
      <div className="candidate__head">
        {/* 再生系の ▶ は各候補行と同じく左端に揃える (押しやすさ・視線の一貫性)。 */}
        <button
          type="button"
          className="candidate__play"
          title={t("candidate.playSegment.title")}
          onClick={() => container.playback.playRegion(seg.start, seg.end)}
        >
          {t("candidate.segment")}
        </button>
        <span className="candidate__title">
          {t("candidate.title")} · {fmtTime(seg.start)}–{fmtTime(seg.end)}
        </span>
        <button
          type="button"
          className="chip__x"
          title={t("candidate.close.title")}
          onClick={close}
        >
          ×
        </button>
      </div>

      {!rec || rec.candidates.length === 0 ? (
        <p className="candidate__empty">{t("candidate.empty")}</p>
      ) : (
        <ul className="candidate__list">
          {rec.candidates.map((c) => {
            const color = speakerColor(c.cluster, speakers, palette.speakers);
            const current = c.cluster === seg.speaker;
            const pct = Math.max(0, Math.min(1, c.score)) * 100;
            return (
              <li key={c.cluster} className="candidate__row">
                <button
                  type="button"
                  className="candidate__play"
                  title={t("candidate.preview.title", { cluster: c.cluster })}
                  onClick={() => previewSpeaker(c.cluster)}
                >
                  ▶
                </button>
                <button
                  type="button"
                  className={`candidate__pick${current ? " candidate__pick--current" : ""}`}
                  title={
                    current
                      ? t("candidate.current.title")
                      : t("candidate.moveTo.title", { cluster: c.cluster })
                  }
                  onClick={() => moveTo(c.cluster)}
                >
                  <span className="chip__dot" style={{ background: color }} />
                  <span className="candidate__name" title={c.cluster}>
                    {c.cluster}
                  </span>
                  <span className="candidate__bar">
                    <span
                      className="candidate__bar-fill"
                      style={{ width: `${pct}%`, background: color }}
                    />
                  </span>
                  <span className="candidate__score">{c.score.toFixed(2)}</span>
                  <span className="candidate__cur">{current ? t("candidate.current") : ""}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <button
        type="button"
        className={`candidate__novel${rec?.novel ? " candidate__novel--suggest" : ""}`}
        title={t("candidate.novel.title")}
        onClick={moveToNew}
      >
        {t("candidate.novel")}
        {rec?.novel && <span className="candidate__cur">{t("candidate.recommended")}</span>}
      </button>
    </div>
  );
}
