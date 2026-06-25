import { create } from "zustand";
import type { AudioDecoder } from "../application/ports.ts";
import type { DecodedAudio } from "../domain/types.ts";

interface AudioState {
  audio: DecodedAudio | null;
  name: string | null;
  /** 元ファイル。自動分離 (diarize) でバックエンドへ渡す。 */
  file: File | null;
  /**
   * File System Access のファイルハンドル (対応ブラウザで音声を開いたとき)。
   * autosave がドラフトと一緒に保存し、再開時に1クリックで音声を自動復元する元。
   */
  handle: FileSystemFileHandle | null;
  /** 再生用の blob URL。 */
  url: string | null;
  /** 動画ファイルの場合 true。<video> 要素でプレビューを表示する。 */
  isVideo: boolean;
  loadingMsg: string | null;
  load(file: File, decoder: AudioDecoder, handle?: FileSystemFileHandle): Promise<DecodedAudio>;
}

function isVideoFile(file: File): boolean {
  return file.type.startsWith("video/") || /\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(file.name);
}

export const useAudioStore = create<AudioState>((set, get) => ({
  audio: null,
  name: null,
  file: null,
  handle: null,
  url: null,
  isVideo: false,
  loadingMsg: null,
  async load(file, decoder, handle) {
    set({ loadingMsg: "デコード中…" });
    const video = isVideoFile(file);
    let audio: DecodedAudio;
    try {
      audio = await decoder.decode(file);
    } catch (e) {
      // 動画コンテナ (mp4/mov 等) は decodeAudioData で落ちることが多い。
      // 固まらせず明示する (波形は出ないが video プレビュー+手動アノテは可能)。
      set({
        loadingMsg: video
          ? `音声トラックをデコードできませんでした (${file.name})。動画の波形表示には ffmpeg 経路が必要です。`
          : `デコードに失敗しました (${file.name})。`,
      });
      throw e;
    }
    // デコード成功後にだけ旧 URL を破棄 (失敗時は現在のメディアを壊さない)。
    const prevUrl = get().url;
    if (prevUrl) URL.revokeObjectURL(prevUrl);
    set({
      audio,
      name: file.name,
      file,
      handle: handle ?? null,
      url: URL.createObjectURL(file),
      isVideo: video,
      loadingMsg: null,
    });
    return audio;
  },
}));
