// 音声 / 動画 / RTTM / voxmap.json の読み込み振り分け。拡張子・MIME で判定する。
import { container } from "../../app/container.ts";
import { parseRttm } from "../../domain/rttm.ts";
import { type ParsedSidecar, parseSidecar } from "../../domain/sidecar.ts";
import { useAudioStore } from "../../state/audioStore.ts";
import { useCatchStore } from "../../state/catchStore.ts";
import { useEditOpsStore } from "../../state/editOpsStore.ts";
import { useEditorStore } from "../../state/editorStore.ts";
import { useNoticeStore } from "../../state/noticeStore.ts";
import { useSessionStore } from "../../state/sessionStore.ts";
import { t } from "../../ui/i18n/t.ts";

function stripExt(name: string): string {
  return name.replace(/\.[^.]+$/, "");
}

function isJson(file: File): boolean {
  return /\.json$/i.test(file.name) || file.type === "application/json";
}

function isRttm(file: File): boolean {
  return /\.(rttm|txt)$/i.test(file.name);
}

function isAudio(file: File): boolean {
  return file.type.startsWith("audio/") || /\.(wav|mp3|m4a|ogg|flac|aac)$/i.test(file.name);
}

function isVideo(file: File): boolean {
  return file.type.startsWith("video/") || /\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(file.name);
}

export async function loadAudioFile(file: File, handle?: FileSystemFileHandle): Promise<void> {
  await useAudioStore.getState().load(file, container.audioDecoder, handle);
  const ed = useEditorStore.getState();
  if (!ed.segments.length) ed.setFileId(stripExt(file.name));
}

// File System Access のファイルピッカー種別 (音声 + 動画)。
// accept のキーは具体的な MIME 型のみ。ワイルドカード ("audio/*") は Chrome が TypeError で弾く。
// description は現在言語に追従させたいので、ピッカーを開くたびに t() で生成する。
function audioPickerTypes(): FilePickerAcceptType[] {
  return [
    {
      description: t("picker.audioVideo"),
      accept: {
        "audio/wav": [".wav"],
        "audio/mpeg": [".mp3"],
        "audio/mp4": [".m4a"],
        "audio/ogg": [".ogg"],
        "audio/flac": [".flac"],
        "audio/aac": [".aac"],
        "video/mp4": [".mp4", ".m4v"],
        "video/quicktime": [".mov"],
        "video/x-matroska": [".mkv"],
        "video/webm": [".webm"],
        "video/x-msvideo": [".avi"],
      },
    },
  ];
}

/**
 * 対応ブラウザ (Chromium 系) では showOpenFilePicker で開き、ファイルハンドルを保存する
 * (再開時の音声自動復元に使う)。非対応なら false を返し、呼び出し側が <input> にフォールバック。
 * 戻り値: true = ピッカーで処理した (ユーザーキャンセル含む) / false = <input> へフォールバック。
 */
export async function pickAudio(): Promise<boolean> {
  if (typeof window.showOpenFilePicker !== "function") return false;
  let handle: FileSystemFileHandle;
  try {
    [handle] = await window.showOpenFilePicker({ types: audioPickerTypes(), multiple: false });
  } catch (e) {
    // ユーザーキャンセル (AbortError) は何もしない。それ以外の失敗は <input> へフォールバック。
    if (e instanceof DOMException && e.name === "AbortError") return true;
    return false;
  }
  const file = await handle.getFile();
  await loadAudioFile(file, handle).catch(() => {});
  return true;
}

/**
 * 保存しておいたファイルハンドルから音声を復元する (1クリック)。
 * 読み取り許可が無ければユーザー操作中に requestPermission で1回求める。失敗時 false。
 */
export async function restoreAudioFromHandle(handle: FileSystemFileHandle): Promise<boolean> {
  try {
    if ((await handle.queryPermission({ mode: "read" })) !== "granted") {
      if ((await handle.requestPermission({ mode: "read" })) !== "granted") return false;
    }
    const file = await handle.getFile();
    await loadAudioFile(file, handle);
    return true;
  } catch {
    return false;
  }
}

export async function loadRttmFile(file: File): Promise<void> {
  const text = await file.text();
  const { fileId, segments } = parseRttm(text);
  useCatchStore.getState().clear(); // 外部 RTTM は罠なし
  useEditorStore.getState().importSegments(segments, fileId ?? stripExt(file.name));
}

/**
 * パース済み sidecar から編集状態を復元する (ファイル読み込み・autosave 復元で共有)。
 * source は通知に出す読み込み元の名前 (ファイル名 / "自動保存")。
 */
export function restoreFromParsed(parsed: ParsedSidecar, source: string): void {
  useCatchStore.getState().clear(); // 罠はセッション内のみ。再開時は持ち越さない
  useEditorStore.getState().importSegments(parsed.segments, parsed.fileId);

  // 作業コストを引き継ぐ (importSegments が editOps を 0 に戻した後で seed する)。
  // activeSec / createdAt は sessionStore 側へ。後から音声ロードの start() が走っても消えない。
  if (parsed.cost) {
    useEditOpsStore.getState().seed(parsed.cost.editOpsDetail);
    useSessionStore.getState().resume(parsed.cost.activeSec, parsed.createdAt, parsed.cost.wallSec);
  }

  const notes: string[] = [];
  if (parsed.tampered) notes.push(t("notice.tampered"));
  notes.push(parsed.complete ? t("notice.complete") : t("notice.draft"));

  // 保存時の音声が未読み込みなら案内を追加。
  // ブラウザは絶対パスを取れないので自動読み込みは不可。ファイル名だけ案内する。
  // audioName がない旧形式でも「音声が未ロード」なら汎用案内を出す。
  const loadedName = useAudioStore.getState().name;
  if (parsed.audioName && loadedName !== parsed.audioName) {
    notes.push(t("notice.audioMissingNamed", { audioName: parsed.audioName }));
  } else if (!parsed.audioName && !loadedName) {
    notes.push(t("notice.audioMissing"));
  }

  useNoticeStore
    .getState()
    .notify(
      t("notice.loaded", { source, notes: notes.join(" / ") }),
      parsed.tampered ? "warn" : "info",
    );
}

/** voxmap.json (savepoint) を読み込んで status まで復元する。json でなければ false。 */
export async function loadSidecarFile(file: File): Promise<boolean> {
  const text = await file.text();
  const parsed = parseSidecar(text);
  if (!parsed) return false;
  restoreFromParsed(parsed, file.name);
  return true;
}

/** ドラッグ&ドロップ等で受け取ったファイル群を振り分けて読み込む。 */
export async function loadDropped(files: FileList | File[]): Promise<void> {
  for (const file of Array.from(files)) {
    try {
      // .json は voxmap.json として試し、違えば素通り。
      if (isJson(file)) {
        if (await loadSidecarFile(file)) continue;
      }
      if (isRttm(file)) await loadRttmFile(file);
      else if (isAudio(file) || isVideo(file)) await loadAudioFile(file);
    } catch {
      // デコード失敗等は audioStore.loadingMsg に表示済み。次のファイルへ続行。
    }
  }
}
