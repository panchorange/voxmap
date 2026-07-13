import { useEffect, useRef, useState } from "react";
import { container, usingStubDiarization } from "./app/container.ts";
import { keptPhantoms, stripUntouchedPhantoms } from "./domain/catch.ts";
import { serializeRttm } from "./domain/rttm.ts";
import { parseSidecar } from "./domain/sidecar.ts";
import { hasUnverified, unverified } from "./domain/status.ts";
import { DiarizeOverlay } from "./features/diarize/DiarizeOverlay.tsx";
import { type DiarizeOutcome, runDiarization } from "./features/diarize/runDiarization.ts";
import { SpeakerMappingDialog } from "./features/diarize/SpeakerMappingDialog.tsx";
import { ExportPanel } from "./features/io/ExportPanel.tsx";
import {
  loadAudioFile,
  loadDropped,
  loadRttmFile,
  loadSidecarFile,
  pickAudio,
  restoreAudioFromHandle,
  restoreFromParsed,
} from "./features/io/loadFiles.ts";
import { SaveStatus } from "./features/io/SaveStatus.tsx";
import { sidecarText } from "./features/io/sidecarSnapshot.ts";
import { ModeToggle } from "./features/mode/ModeToggle.tsx";
import { CandidatePanel } from "./features/recommend/CandidatePanel.tsx";
import { SegmentList } from "./features/segment-list/SegmentList.tsx";
import { BulkBar } from "./features/speakers/BulkBar.tsx";
import { SpeakerChips } from "./features/speakers/SpeakerChips.tsx";
import { Transport } from "./features/transport/Transport.tsx";
import { useKeyboard } from "./features/waveform/useKeyboard.ts";
import { WaveformCanvas } from "./features/waveform/WaveformCanvas.tsx";
import { type DraftRecord, deleteDraft, listDrafts } from "./infrastructure/draftStore.ts";
import { playGalleryClip } from "./infrastructure/galleryPreview.ts";
import { useAudioStore } from "./state/audioStore.ts";
import { useBackendStore } from "./state/backendStore.ts";
import { useCatchStore } from "./state/catchStore.ts";
import { useEditorStore } from "./state/editorStore.ts";
import { useModeStore } from "./state/modeStore.ts";
import { useNoticeStore } from "./state/noticeStore.ts";
import { LangSwitcher } from "./ui/i18n/LangSwitcher.tsx";
import { useT } from "./ui/i18n/t.ts";
import { BlackDiamondScene } from "./ui/theme/BlackDiamondScene.tsx";
import { ThemeSwitcher } from "./ui/theme/ThemeSwitcher.tsx";
import { useTheme } from "./ui/theme/useTheme.ts";
import { YozakuraScene } from "./ui/theme/YozakuraScene.tsx";
import { YushaScene } from "./ui/theme/YushaScene.tsx";

interface ExportData {
  fileId: string;
  /** 途中保存 (savepoint) では null。RTTM はゲートを通った完成時のみ生成する。 */
  rttm: string | null;
  sidecar: string | null;
  /** segments から導出した完成判定 (auto が0件)。フラグの自己申告ではない。 */
  complete: boolean;
  kind: "draft" | "final";
}

type TFn = ReturnType<typeof useT>;

/** epoch ms を「○分前 / ○時間前」表記に。復元バナーの新しさ表示に使う。 */
function minutesAgo(ms: number, t: TFn): string {
  const min = Math.max(0, Math.round((Date.now() - ms) / 60000));
  if (min < 1) return t("common.justNow");
  if (min < 60) return t("common.minutesAgo", { n: min });
  return t("common.hoursAgo", { n: Math.round(min / 60) });
}

// 完成書き出し: RTTM (標準) + voxmap.json。annotation では未検証 phantom を除いてから。
function buildFinal(): ExportData {
  const ed = useEditorStore.getState();
  if (useModeStore.getState().mode !== "annotation") {
    return {
      fileId: ed.fileId,
      rttm: serializeRttm(ed.segments, ed.fileId),
      sidecar: null,
      complete: true,
      kind: "final",
    };
  }
  const cleaned = stripUntouchedPhantoms(ed.segments, useCatchStore.getState().trials);
  return {
    fileId: ed.fileId,
    rttm: serializeRttm(cleaned, ed.fileId),
    sidecar: sidecarText(cleaned),
    complete: !hasUnverified(cleaned),
    kind: "final",
  };
}

// 途中保存 (savepoint): voxmap.json のみ。全区間を忠実に保存し、後で読み込んで再開できる。
// RTTM は出さない (完成RTTMはゲート通過時のみ生成される、を担保するため)。
function buildSavepoint(): ExportData {
  const ed = useEditorStore.getState();
  return {
    fileId: ed.fileId,
    rttm: null,
    sidecar: sidecarText(ed.segments),
    complete: !hasUnverified(ed.segments),
    kind: "draft",
  };
}

export function App() {
  const [theme, setTheme] = useTheme();
  const t = useT();
  const audioName = useAudioStore((s) => s.name);
  const loadingMsg = useAudioStore((s) => s.loadingMsg);
  const hasAudio = useAudioStore((s) => s.file !== null);
  const isVideo = useAudioStore((s) => s.isVideo);
  const videoUrl = useAudioStore((s) => s.url);
  const durationSec = useAudioStore((s) => s.audio?.duration ?? 0);
  const segments = useEditorStore((s) => s.segments);
  const annotation = useModeStore((s) => s.mode === "annotation");
  const notice = useNoticeStore((s) => s.message);
  const noticeKind = useNoticeStore((s) => s.kind);

  const [exportData, setExportData] = useState<ExportData | null>(null);
  const [gateCount, setGateCount] = useState(0); // >0 のとき未検証ゲートを表示
  const [keptIds, setKeptIds] = useState<string[]>([]); // kept phantom の警告対象
  const [dragOver, setDragOver] = useState(false);
  const [diarizing, setDiarizing] = useState(false);
  const [speakerAuto, setSpeakerAuto] = useState(true); // true = AUTO (話者数推定)
  const [speakerText, setSpeakerText] = useState("2"); // 手動時の話者数 (自由入力)
  const [minDurationOn, setMinDurationOn] = useState(0.3); // 短区間抑制の閾値 (秒)
  const [mapping, setMapping] = useState<DiarizeOutcome | null>(null); // 一括対応ポップアップ
  const [error, setError] = useState<string | null>(null);
  const [draftPrompt, setDraftPrompt] = useState<DraftRecord | null>(null); // 起動時の復元候補
  useKeyboard();
  const audioInputRef = useRef<HTMLInputElement>(null);
  const rttmInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // 話者数の手動入力バリデーション: 1〜MAX_SPEAKERS の整数のみ許可。AUTO 時は無視。
  const MAX_SPEAKERS = 30;
  // 短区間抑制の閾値。0 = OFF (無効化)、以降 0.1 刻み。select にして無効値を構造的に排除する。
  const MIN_DURATION_OPTIONS = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
  const speakerCount = /^\d+$/.test(speakerText) ? Number(speakerText) : Number.NaN;
  const speakerValid =
    speakerAuto ||
    (Number.isInteger(speakerCount) && speakerCount >= 1 && speakerCount <= MAX_SPEAKERS);

  // 動画ファイル読み込み時: PlaybackController を <video> 要素に切り替える。
  // 音声に戻った場合は null を渡して内部 Audio に差し戻す。src は wiring の
  // attach() が同じ要素に再設定するので、isVideo の切替時だけ実行すればよい。
  useEffect(() => {
    container.playback.setMediaElement(isVideo ? (videoRef.current ?? null) : null);
  }, [isVideo]);

  // backend のデバイスを 1 回取得 (分離所要の推定に使う)。スタブ時は取得失敗で null のまま。
  useEffect(() => {
    if (!usingStubDiarization) void useBackendStore.getState().fetchHealth();
  }, []);

  // 起動時、編集が空なら直近の自動保存を復元候補として提示する (非ブロッキング)。
  useEffect(() => {
    if (useEditorStore.getState().segments.length) return;
    void listDrafts().then((ds) => {
      if (ds[0]) setDraftPrompt(ds[0]);
    });
  }, []);

  const restoreDraft = async () => {
    const dp = draftPrompt;
    if (!dp) return;
    setDraftPrompt(null);
    const parsed = parseSidecar(dp.sidecar);
    if (parsed) restoreFromParsed(parsed, t("notice.autosaveSource"));
    // 音声ハンドルがあれば1クリック (この onClick が user gesture) で自動復元を試みる。
    if (dp.audioHandle) {
      const ok = await restoreAudioFromHandle(dp.audioHandle);
      useNoticeStore
        .getState()
        .notify(t(ok ? "notice.restored" : "notice.restoreAudioFailed"), ok ? "info" : "warn");
    }
  };
  const discardDraft = () => {
    if (draftPrompt) void deleteDraft(draftPrompt.fileId);
    setDraftPrompt(null);
  };

  // 完成書き出し: annotation モードで (1) 未検証 (auto) が残っていればハードブロック、
  // (2) 罠 (phantom) を残したまま (kept) なら駆け込み警告、で止める。抜け道は「途中保存」。
  const onExportClick = () => {
    if (annotation && hasUnverified(segments)) {
      setGateCount(unverified(segments).length);
      return;
    }
    if (annotation) {
      const kept = keptPhantoms(useCatchStore.getState().trials, segments);
      if (kept.length) {
        setKeptIds(kept.map((s) => s.id));
        return;
      }
    }
    setExportData(buildFinal());
  };
  // 未検証ゲート: 最初の auto を選択してジャンプ。
  const jumpToFirstUnverified = () => {
    const first = unverified(useEditorStore.getState().segments)[0];
    if (first) {
      useEditorStore.getState().selectSingle(first.id);
      container.playback.seek(first.start);
    }
    setGateCount(0);
  };
  // kept 警告: 最初の罠区間を選択してジャンプ (再生して聴き直させる)。
  const reviewFirstKept = () => {
    const id = keptIds[0];
    const seg = id ? useEditorStore.getState().segments.find((s) => s.id === id) : undefined;
    if (seg) {
      useEditorStore.getState().selectSingle(seg.id);
      container.playback.playRegion(seg.start, seg.end);
    }
    setKeptIds([]);
  };

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: 画面全体への D&D
    <div
      className="app"
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        if (e.dataTransfer.files.length) void loadDropped(e.dataTransfer.files);
      }}
    >
      {theme === "yusha" && <YushaScene />}
      {theme === "yozakura" && <YozakuraScene />}
      {theme === "blackdiamond" && <BlackDiamondScene />}
      {dragOver && <div className="dropzone-overlay">{t("dropzone.hint")}</div>}

      <header className={`app__header${annotation ? " app__header--annotation" : ""}`}>
        <div className="app__tools">
          <h1 className="app__title">voxmap-studio</h1>
          {annotation && (
            <span className="badge badge--annotation">{t("header.badge.annotation")}</span>
          )}
          {audioName && (
            <span className="faint" style={{ fontSize: "0.7rem" }}>
              {audioName}
            </span>
          )}
          <SaveStatus />
        </div>
        <div className="app__tools">
          <input
            ref={audioInputRef}
            type="file"
            accept="audio/*,video/*"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) loadAudioFile(f).catch(() => {});
            }}
          />
          <input
            ref={rttmInputRef}
            type="file"
            accept=".rttm,.txt,.json"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              if (/\.json$/i.test(f.name)) void loadSidecarFile(f);
              else void loadRttmFile(f);
            }}
          />
          <button
            type="button"
            className="btn"
            onClick={async () => {
              // 対応ブラウザは showOpenFilePicker (ハンドル取得→音声自動復元の元)。
              // 非対応なら <input> にフォールバック。
              if (!(await pickAudio())) audioInputRef.current?.click();
            }}
          >
            {t("header.audioVideo")}
          </button>
          <button
            type="button"
            className="btn"
            title={t("header.rttmJson.title")}
            onClick={() => rttmInputRef.current?.click()}
          >
            {t("header.rttmJson")}
          </button>
          <div className="speaker-count" title={t("header.speakerCount.title")}>
            <span className="speaker-count__label">{t("header.speakerCount")}</span>
            <button
              type="button"
              className={`btn btn--toggle${speakerAuto ? " is-on" : ""}`}
              disabled={!hasAudio || diarizing}
              aria-pressed={speakerAuto}
              onClick={() => setSpeakerAuto((v) => !v)}
            >
              AUTO
            </button>
            <input
              type="text"
              inputMode="numeric"
              className={`speaker-count__input${speakerAuto ? "" : " is-active"}${speakerValid ? "" : " is-invalid"}`}
              disabled={!hasAudio || diarizing || speakerAuto}
              value={speakerText}
              title={t("header.speakerCount.range", { max: MAX_SPEAKERS })}
              onFocus={() => setSpeakerAuto(false)}
              onChange={(e) => setSpeakerText(e.target.value)}
            />
          </div>
          <div className="speaker-count" title={t("header.minDurationOn.title")}>
            <span className="speaker-count__label">{t("header.minDurationOn")}</span>
            <select
              className="select"
              disabled={!hasAudio || diarizing}
              value={minDurationOn}
              onChange={(e) => setMinDurationOn(Number(e.target.value))}
            >
              {MIN_DURATION_OPTIONS.map((v) => (
                <option key={v} value={v}>
                  {v === 0 ? "OFF" : `${v.toFixed(1)}s`}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="btn btn--magic"
            disabled={!hasAudio || diarizing || !speakerValid}
            title={
              speakerValid
                ? t("header.diarize.title")
                : t("header.diarize.invalid", { max: MAX_SPEAKERS })
            }
            onClick={async () => {
              setError(null);
              setDiarizing(true);
              try {
                const outcome = await runDiarization(
                  speakerAuto ? null : speakerCount,
                  minDurationOn,
                );
                // 既知話者に対応づく提案が1つでもあれば一括対応ポップアップを出す。
                if (outcome.clusterMapping.some((m) => m.speaker !== null)) {
                  setMapping(outcome);
                }
              } catch (e) {
                setError(t("diarize.failed", { msg: e instanceof Error ? e.message : String(e) }));
              } finally {
                setDiarizing(false);
              }
            }}
          >
            {diarizing ? t("header.diarize.running") : t("header.diarize")}
            {usingStubDiarization && <span className="badge">stub</span>}
          </button>
          {annotation && (
            <button
              type="button"
              className="btn"
              disabled={!segments.length}
              title={t("header.savepoint.title")}
              onClick={() => setExportData(buildSavepoint())}
            >
              {t("header.savepoint")}
            </button>
          )}
          <button
            type="button"
            className="btn btn--accent"
            disabled={!segments.length}
            title={
              annotation ? t("header.export.title.annotation") : t("header.export.title.viewer")
            }
            onClick={onExportClick}
          >
            {t("header.export")}
          </button>
          <ModeToggle />
          <ThemeSwitcher value={theme} onChange={setTheme} />
          <LangSwitcher />
        </div>
      </header>

      {loadingMsg && <p className="muted">{loadingMsg}</p>}
      {error && (
        <button type="button" className="error-banner" onClick={() => setError(null)}>
          {error}
        </button>
      )}
      {notice && (
        <button
          type="button"
          className={`notice-banner${noticeKind === "warn" ? " notice-banner--warn" : ""}`}
          onClick={() => useNoticeStore.getState().clear()}
        >
          {notice}
        </button>
      )}
      {draftPrompt && (
        <div className="notice-banner restore-banner">
          <span>
            {t("restore.prompt", {
              fileId: draftPrompt.fileId,
              ago: minutesAgo(draftPrompt.savedAt, t),
            })}
            {draftPrompt.audioHandle && t("restore.withAudio")}
          </span>
          <span className="restore-banner__actions">
            <button type="button" className="btn btn--accent" onClick={() => void restoreDraft()}>
              {t("restore.restore")}
            </button>
            <button type="button" className="btn" onClick={discardDraft}>
              {t("restore.discard")}
            </button>
          </span>
        </div>
      )}

      {/* 動画ファイルのとき: 波形の上にプレビューを表示 */}
      {isVideo && videoUrl && (
        <div className="video-preview">
          {/* biome-ignore lint/a11y/useMediaCaption: アノテーション用のプレビュー */}
          <video ref={videoRef} src={videoUrl} className="video-preview__player" />
        </div>
      )}

      <section className="panel" style={{ padding: 8, position: "relative" }}>
        <Transport />
        <WaveformCanvas />
        {diarizing && <DiarizeOverlay durationSec={durationSec} />}
      </section>

      <div style={{ marginTop: 12 }}>
        <SpeakerChips />
      </div>
      <CandidatePanel />
      <BulkBar />

      <section style={{ marginTop: 12 }}>
        <SegmentList />
      </section>

      {exportData !== null && (
        <ExportPanel
          fileId={exportData.fileId}
          rttm={exportData.rttm}
          sidecar={exportData.sidecar}
          kind={exportData.kind}
          complete={exportData.complete}
          onClose={() => setExportData(null)}
        />
      )}

      {mapping !== null && (
        <SpeakerMappingDialog
          mapping={mapping.clusterMapping}
          onPreview={(cluster) => {
            // そのクラスタの最長セグメントを最大 5 秒だけ試聴 (声を確認してから選ぶ)。
            const segs = useEditorStore.getState().segments.filter((s) => s.speaker === cluster);
            if (!segs.length) return;
            const rep = segs.reduce((a, b) => (b.end - b.start > a.end - a.start ? b : a));
            container.playback.playRegion(rep.start, Math.min(rep.end, rep.start + 5));
          }}
          onPreviewSpeaker={(name) => playGalleryClip(name)}
          onApply={(pairs) => {
            useEditorStore.getState().applySpeakerMapping(pairs);
            setMapping(null);
          }}
          onClose={() => setMapping(null)}
        />
      )}

      {gateCount > 0 && (
        // biome-ignore lint/a11y/noStaticElementInteractions: 背景クリックで閉じる
        // biome-ignore lint/a11y/useKeyWithClickEvents: モーダル背景
        <div className="modal__backdrop" onClick={() => setGateCount(0)}>
          {/* biome-ignore lint/a11y/noStaticElementInteractions: ダイアログ本体 */}
          {/* biome-ignore lint/a11y/useKeyWithClickEvents: 伝播停止のみ */}
          <div className="modal panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal__head">
              <h3 className="app__title">{t("gate.title")}</h3>
            </div>
            <p style={{ fontSize: "0.85rem" }}>{t("gate.body", { n: gateCount })}</p>
            <div className="modal__actions">
              <button type="button" className="btn" onClick={() => setGateCount(0)}>
                {t("common.close")}
              </button>
              <button
                type="button"
                className="btn"
                title={t("gate.savepoint.title")}
                onClick={() => {
                  setGateCount(0);
                  setExportData(buildSavepoint());
                }}
              >
                {t("gate.savepoint")}
              </button>
              <button type="button" className="btn btn--accent" onClick={jumpToFirstUnverified}>
                {t("gate.jump")}
              </button>
            </div>
          </div>
        </div>
      )}

      {keptIds.length > 0 && (
        // biome-ignore lint/a11y/noStaticElementInteractions: 背景クリックで閉じる
        // biome-ignore lint/a11y/useKeyWithClickEvents: モーダル背景
        <div className="modal__backdrop" onClick={() => setKeptIds([])}>
          {/* biome-ignore lint/a11y/noStaticElementInteractions: ダイアログ本体 */}
          {/* biome-ignore lint/a11y/useKeyWithClickEvents: 伝播停止のみ */}
          <div className="modal panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal__head">
              <h3 className="app__title">{t("kept.title")}</h3>
            </div>
            <p style={{ fontSize: "0.85rem" }}>{t("kept.body", { n: keptIds.length })}</p>
            <div className="modal__actions">
              <button type="button" className="btn" onClick={() => setKeptIds([])}>
                {t("common.close")}
              </button>
              <button type="button" className="btn btn--accent" onClick={reviewFirstKept}>
                {t("kept.review")}
              </button>
              <button
                type="button"
                className="btn btn--danger"
                title={t("kept.exportAnyway.title")}
                onClick={() => {
                  setKeptIds([]);
                  setExportData(buildFinal());
                }}
              >
                {t("kept.exportAnyway")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
