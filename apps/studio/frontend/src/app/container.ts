// 合成ルート (composition root)。アダプタをポートに束ねて UI に渡す。
// 本番接続時はここで Stub -> Http に差し替えるだけ。

import type { AudioDecoder, DiarizationService } from "../application/ports.ts";
import { HttpDiarization } from "../infrastructure/httpDiarization.ts";
import { PlaybackController } from "../infrastructure/playbackController.ts";
import { StubDiarization } from "../infrastructure/stubDiarization.ts";
import { WebAudioDecoder } from "../infrastructure/webAudioDecoder.ts";

export interface Container {
  audioDecoder: AudioDecoder;
  diarization: DiarizationService;
  playback: PlaybackController;
}

// backend を使うか。VITE_USE_STUB=1 でスタブ (backend 無しでフロント単体動作)。
export const usingStubDiarization = import.meta.env.VITE_USE_STUB === "1";
const useStub = usingStubDiarization;

export function createContainer(): Container {
  return {
    audioDecoder: new WebAudioDecoder(),
    diarization: useStub ? new StubDiarization() : new HttpDiarization(),
    playback: new PlaybackController(),
  };
}

/** アプリ全体で共有する単一インスタンス。 */
export const container = createContainer();
