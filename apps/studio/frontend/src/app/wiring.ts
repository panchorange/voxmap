// 合成ルートの配線。アプリ起動時に1回だけ呼ぶ (main.tsx)。
// 再生コントローラ (infrastructure) と store を疎結合のまま繋ぐ唯一の場所。
import { wireFollowEdits } from "../features/recommend/followEdits.ts";
import { useAudioStore } from "../state/audioStore.ts";
import { useCoverageStore } from "../state/coverageStore.ts";
import { useEditorStore } from "../state/editorStore.ts";
import { usePlaybackStore } from "../state/playbackStore.ts";
import { useSessionStore } from "../state/sessionStore.ts";
import { container } from "./container.ts";

let wired = false;

export function wirePlayback(): void {
  if (wired) return; // 冪等 (StrictMode の二重実行・HMR 対策)
  wired = true;

  const pb = usePlaybackStore.getState();
  // 再生位置の通知 + 再生カバレッジ記録 (前回 tick との区間を埋める)。
  let prevT = pb.currentTime;
  container.playback.onTick = (t) => {
    if (usePlaybackStore.getState().playing) {
      useCoverageStore.getState().mark(prevT, t, container.playback.rate);
    }
    prevT = t;
    pb.setCurrentTime(t);
  };
  container.playback.onPlayingChange = pb.setPlaying;
  container.playback.onRateChange = pb.setRate;

  // 音声ロード時に blob URL を attach。
  let prevUrl = useAudioStore.getState().url;
  if (prevUrl) container.playback.attach(prevUrl);
  // 新しい音声のデコード完了でカバレッジをリセット (duration が確定する)。
  let prevAudio = useAudioStore.getState().audio;
  if (prevAudio) useCoverageStore.getState().reset(prevAudio.duration);
  // セッションが属する annotate 対象 (fileId)。同じファイルの音声再アタッチでは
  // start() を呼ばない = activeSec を巻き戻さない。別ファイルに切り替えたときだけ新セッション。
  let sessionFileId: string | null = prevAudio ? useEditorStore.getState().fileId : null;
  useAudioStore.subscribe((s) => {
    if (s.url && s.url !== prevUrl) {
      prevUrl = s.url;
      container.playback.attach(s.url);
    }
    if (s.audio && s.audio !== prevAudio) {
      prevAudio = s.audio;
      prevT = 0;
      useCoverageStore.getState().reset(s.audio.duration);
      // 別ファイルを開いたときだけ新セッション開始 (コスト計測。savepoint 再開もここを通る)。
      // 「JSON/RTTM を先に読んで編集 → あとから音声を読む」順でも、同じ fileId なら
      // 既存セッションを維持し activeSec を保つ (audio 差し替え≠新セッション)。
      const fileId = useEditorStore.getState().fileId;
      if (fileId !== sessionFileId) {
        sessionFileId = fileId;
        useSessionStore.getState().start(performance.now(), new Date().toISOString());
      }
    }
  });

  // コスト計測 (§4): 操作を記録し、1秒ごとに idle 除外でアクティブ時間を積む。
  // pointerdown は click/drag を、wheel はズーム/パンを拾う。passive で描画を妨げない。
  const onActivity = () => useSessionStore.getState().markActivity(performance.now());
  window.addEventListener("pointerdown", onActivity, { passive: true });
  window.addEventListener("keydown", (e) => {
    onActivity();
    if (e.code === "Space" && !e.repeat && (e.target as Element).tagName !== "INPUT") {
      e.preventDefault();
      container.playback.toggle();
    }
  });
  window.addEventListener("wheel", onActivity, { passive: true });
  setInterval(() => {
    useSessionStore.getState().tick(performance.now(), usePlaybackStore.getState().playing);
  }, 1000);

  // 編集追従: segment の geometry 変化で怪しさ/レコメンドを再計算する (分離後のみ)。
  wireFollowEdits();
}
