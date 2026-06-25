import { useState } from "react";
import type { ClusterMapping } from "../../domain/types.ts";
import { useT } from "../../ui/i18n/t.ts";

// 行ごとに「新規話者 (= auto ラベルのまま)」を選べる番兵値。
const NOVEL = "__novel__";

type Props = {
  /** バックエンドの一括対応提案。各行の候補は scores (τ以上の上位 k 件)。 */
  mapping: ClusterMapping[];
  /** ▶ (左): そのクラスタ (SPEAKER_xx) の代表セグメントを試聴する。 */
  onPreview(cluster: string): void;
  /** ▶ (右): 選択中の既知話者の代表クリップを試聴する。 */
  onPreviewSpeaker(name: string): void;
  /** [はい]: cluster -> 既知話者名 のリネームを適用する。 */
  onApply(pairs: { from: string; to: string }[]): void;
  /** [いいえ] / 背景クリック: 対応づけせず閉じる (auto ラベルのまま)。 */
  onClose(): void;
};

/**
 * 分離直後の一括対応 確認ポップアップ (設計 §6.1)。
 * 候補は各クラスタの top-k (τ以上) のみ。棄却域 (τ未満) は出さず受け皿は「新規話者」だけ。
 * 自動適用せず、人の [はい] を必ず挟む (誤対応を全区間に広げないため)。
 */
export function SpeakerMappingDialog({
  mapping,
  onPreview,
  onPreviewSpeaker,
  onApply,
  onClose,
}: Props) {
  const t = useT();
  // 行ごとの選択: 提案が既知話者ならその名前、null (τ未満) なら新規。
  const [choice, setChoice] = useState<Record<string, string>>(() =>
    Object.fromEntries(mapping.map((m) => [m.cluster, m.speaker ?? NOVEL])),
  );

  const apply = () => {
    const pairs = mapping
      .map((m) => ({ from: m.cluster, to: choice[m.cluster] ?? NOVEL }))
      .filter((p) => p.to !== NOVEL && p.to !== p.from);
    onApply(pairs);
  };

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: 背景クリックで閉じる
    // biome-ignore lint/a11y/useKeyWithClickEvents: モーダル背景
    <div className="modal__backdrop" onClick={onClose}>
      {/* biome-ignore lint/a11y/noStaticElementInteractions: ダイアログ本体 */}
      {/* biome-ignore lint/a11y/useKeyWithClickEvents: 伝播停止のみ */}
      <div className="modal panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h3 className="app__title">{t("mapping.title")}</h3>
        </div>
        <p style={{ fontSize: "0.85rem" }}>{t("mapping.body")}</p>

        <div className="map-table">
          {mapping.map((m) => {
            const sel = choice[m.cluster] ?? NOVEL;
            // 選択中の話者へのスコアを引く (選択を変えると追従)。新規は対象なし。
            const score =
              sel === NOVEL ? null : (m.scores.find((c) => c.speaker === sel)?.score ?? null);
            const pct = score === null ? 0 : Math.round(Math.max(0, Math.min(1, score)) * 100);
            return (
              <div key={m.cluster} className="map-row">
                <button
                  type="button"
                  className="map-row__play"
                  title={t("mapping.preview.cluster.title")}
                  onClick={() => onPreview(m.cluster)}
                >
                  ▶
                </button>
                <span className="map-row__cluster">{m.cluster}</span>
                <span className="map-row__arrow">→</span>
                <button
                  type="button"
                  className="map-row__play"
                  title={t("mapping.preview.speaker.title")}
                  disabled={sel === NOVEL}
                  onClick={() => sel !== NOVEL && onPreviewSpeaker(sel)}
                >
                  ▶
                </button>
                <select
                  className="map-row__select"
                  value={sel}
                  onChange={(e) => setChoice((c) => ({ ...c, [m.cluster]: e.target.value }))}
                >
                  {/* 候補は top-k (τ以上) のみ。該当なしなら新規話者だけ。 */}
                  {m.scores.map((c) => (
                    <option key={c.speaker} value={c.speaker}>
                      {c.speaker} ({c.score.toFixed(2)})
                    </option>
                  ))}
                  <option value={NOVEL}>{t("mapping.novelOption")}</option>
                </select>
                <span className="map-row__score faint">
                  {score === null
                    ? t("mapping.score.novel")
                    : t("mapping.score.similarity", { score: score.toFixed(2) })}
                </span>
                <span className="map-row__bar">
                  <span className="map-row__bar-fill" style={{ width: `${pct}%` }} />
                </span>
              </div>
            );
          })}
        </div>

        <div className="modal__actions">
          <button type="button" className="btn" onClick={onClose}>
            {t("mapping.no")}
          </button>
          <button type="button" className="btn btn--accent" onClick={apply}>
            {t("mapping.yes")}
          </button>
        </div>
      </div>
    </div>
  );
}
