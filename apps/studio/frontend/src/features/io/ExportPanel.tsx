import { useState } from "react";
import { useT } from "../../ui/i18n/t.ts";

type Props = {
  fileId: string;
  /** 完成書き出しのみ生成。途中保存では null。 */
  rttm: string | null;
  /** 来歴 + QA サマリ (annotation のみ。viewer の RTTM だけのときは null)。 */
  sidecar: string | null;
  kind: "draft" | "final";
  /** segments から導出した完成判定。 */
  complete: boolean;
  onClose(): void;
};

type Tab = "rttm" | "sidecar";

function downloadText(name: string, text: string, type: string): void {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

// 書き出しモーダル。完成=RTTM+voxmap.json、途中保存=voxmap.json のみ。
export function ExportPanel({ fileId, rttm, sidecar, kind, complete, onClose }: Props) {
  const draft = kind === "draft";
  const t = useT();
  const [tab, setTab] = useState<Tab>(rttm ? "rttm" : "sidecar");
  const [copied, setCopied] = useState(false);

  const text = tab === "rttm" ? (rttm ?? "") : (sidecar ?? "");

  const downloadAll = () => {
    if (rttm) downloadText(`${fileId}.rttm`, rttm, "text/plain");
    if (sidecar) downloadText(`${fileId}.voxmap.json`, sidecar, "application/json");
  };

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: 背景クリックで閉じる
    // biome-ignore lint/a11y/useKeyWithClickEvents: モーダル背景
    <div className="modal__backdrop" onClick={onClose}>
      {/* biome-ignore lint/a11y/noStaticElementInteractions: ダイアログ本体 */}
      {/* biome-ignore lint/a11y/useKeyWithClickEvents: 伝播停止のみ */}
      <div className="modal panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h3 className="app__title">
            {draft ? t("export.title.draft") : t("export.title.final")} ({fileId})
          </h3>
          <button type="button" className="btn" onClick={onClose}>
            ✕
          </button>
        </div>
        {sidecar && rttm && (
          <div className="app__tools" style={{ gap: 6 }}>
            <button
              type="button"
              className={`btn${tab === "rttm" ? " btn--accent" : ""}`}
              onClick={() => setTab("rttm")}
            >
              {fileId}.rttm
            </button>
            <button
              type="button"
              className={`btn${tab === "sidecar" ? " btn--accent" : ""}`}
              onClick={() => setTab("sidecar")}
            >
              {fileId}.voxmap.json
            </button>
          </div>
        )}
        <p className="faint" style={{ fontSize: "0.7rem" }}>
          {draft ? (
            <>
              {t("export.body.draft")}
              {!complete && t("export.body.draftUnverified")}
            </>
          ) : (
            t("export.body.final")
          )}
        </p>
        <textarea className="modal__textarea" readOnly value={text} />
        <div className="modal__actions">
          <button
            type="button"
            className="btn"
            onClick={async () => {
              await navigator.clipboard.writeText(text);
              setCopied(true);
            }}
          >
            {copied ? t("export.copied") : t("export.copy")}
          </button>
          <button type="button" className="btn btn--accent" onClick={downloadAll}>
            {rttm && sidecar ? t("export.downloadBoth") : t("export.download")}
          </button>
        </div>
      </div>
    </div>
  );
}
