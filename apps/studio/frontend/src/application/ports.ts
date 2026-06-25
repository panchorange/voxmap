// アプリケーション層が依存するポート (interface)。
// 実装は infrastructure/ が提供し、合成ルート (app/container.ts) で注入する。
// これにより「スタブ自動分離 -> 本番 voxmap パイプライン」が実装差し替えで済む。

import type {
  ClusterMapping,
  DecodedAudio,
  Recommendation,
  Segment,
  Suspicion,
} from "../domain/types.ts";

/** 音声ファイルをデコードしてピークまで計算する。 */
export interface AudioDecoder {
  decode(file: File): Promise<DecodedAudio>;
}

/** 話者分離の結果。区間に加え、既知話者への一括対応提案 (§6.1) を含む。 */
export interface DiarizationResult {
  segments: Segment[];
  /** 各自動クラスタ → 既知話者の対応提案。ギャラリ未設定なら空。 */
  clusterMapping: ClusterMapping[];
  /** 対応先ドロップダウン用の既知話者名一覧。 */
  galleryNames: string[];
}

/** 編集追従の再計算結果。segment id ごとの新しい怪しさ/レコメンド。
 *  null = 追従対象外 (リネーム済み等で再計算できない) → 既存値を保持する。 */
export interface SignalPatch {
  id: string;
  suspicion: Suspicion | null;
  recommendation: Recommendation | null;
}

/** 話者分離。スタブ or /api 経由の本番をアダプタで切り替える。 */
export interface DiarizationService {
  /** 音声から区間 + 一括対応提案を返す。
   *  numSpeakers を渡すと話者数を固定 (null/未指定 = AUTO で推定)。 */
  diarize(file: File, numSpeakers?: number | null): Promise<DiarizationResult>;
  /**
   * 編集後の区間に怪しさ/レコメンドを追従させる (再埋め込みなし、分離後のみ)。
   * 分離前/グリッド無しは空配列を返す。
   */
  recompute(
    segments: { id: string; start: number; end: number; speaker: string }[],
  ): Promise<SignalPatch[]>;
}

/** ASR (将来拡張)。区間ごとのテキスト等を返す想定。 */
export interface AsrService {
  transcribe(file: File, segments: Segment[]): Promise<Segment[]>;
}
