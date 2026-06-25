import type { DiarizationResult, DiarizationService, SignalPatch } from "../application/ports.ts";

// 現状はスタブ (仕様 L80)。本番は httpDiarization に差し替える。
// ギャラリ照合はバックエンド側のため、スタブでは対応提案は空で返す。
export class StubDiarization implements DiarizationService {
  async diarize(_file: File, _numSpeakers?: number | null): Promise<DiarizationResult> {
    return {
      segments: [
        { id: "stub-0", start: 0, end: 2, speaker: "SPEAKER_00", status: "auto" },
        { id: "stub-1", start: 2, end: 4, speaker: "SPEAKER_01", status: "auto" },
      ],
      clusterMapping: [],
      galleryNames: [],
    };
  }

  // スタブには埋め込みグリッドが無いため追従しない (空 = 既存値を保持)。
  async recompute(
    _segments: { id: string; start: number; end: number; speaker: string }[],
  ): Promise<SignalPatch[]> {
    return [];
  }
}
