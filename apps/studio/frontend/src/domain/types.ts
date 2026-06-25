// ドメインの中心エンティティ。純粋な型のみ (React/DOM 非依存)。

/**
 * セグメントの検証状態。アノテーションモードの品質保証に使う。
 * - `auto`: 自動分離 / RTTM 取込のまま未検証 (書き出しゲートで弾く対象)
 * - `edited`: auto を人が境界/話者編集した (= 目を通した)
 * - `confirmed`: 人が明示的に承認 / 手描き新規
 */
export type SegmentStatus = "auto" | "edited" | "confirmed";

/**
 * segment 粒度の怪しさ (混同していそうな所)。ギャラリ不使用・auto クラスタ重心だけで判定。
 * - `intruder`: 別クラスタの方が近い (混入の疑い、最強)
 * - `boundary`: 端っこ・拮抗 (margin が 0〜δ)
 * - `ok`: 問題なし
 */
export type SuspicionLabel = "intruder" | "boundary" | "ok";

export interface Suspicion {
  label: SuspicionLabel;
  /** cos(自クラスタ重心) - max cos(別クラスタ重心)。null = 判定不能。 */
  margin: number | null;
  /** intruder/boundary のとき一番近い別クラスタ (`SPEAKER_xx`)。 */
  nearest: string | null;
}

/** 1 つの話者ライン候補と、その emb_seg への cos。 */
export interface Candidate {
  /** 候補ライン。分離時は `SPEAKER_xx`、一括対応後は人物名へ翻訳される。 */
  cluster: string;
  /** emb_seg との cos 類似度 (confidence)。 */
  score: number;
}

/**
 * segment の話者候補 (§4.3)。候補集合は「今この音声にいる話者ライン」。
 * 分離時に precompute (§7)。境界編集/移動後は backend グリッドで再計算され追従する
 * (followEdits, 再埋め込みなし)。リネーム済み等で再計算できないときは分離時の値を保持。
 */
export interface Recommendation {
  /** 現在の全話者ラインへの cos 降順。自ラインも含む。 */
  candidates: Candidate[];
  /** 最良候補が τ 未満 = どのラインにも似ていない (新規話者の受け皿)。 */
  novel: boolean;
}

/** アノテーション区間。時刻は秒 (float)。 */
export interface Segment {
  id: string;
  start: number;
  end: number;
  /** 話者名。`SPEAKER_00` 形式。 */
  speaker: string;
  /** 検証状態。viewer モードでは無視される。 */
  status: SegmentStatus;
  /** 自動分離が付けた怪しさ (混同地図用)。手描き/RTTM 取込では undefined。 */
  suspicion?: Suspicion;
  /** 自動分離が付けた話者候補 (R パネル用)。手描き/RTTM 取込では undefined。 */
  recommendation?: Recommendation;
}

/**
 * 自動分離クラスタ (SPEAKER_xx) → 既知話者 (ギャラリ) の対応提案。
 * 分離直後の一括対応ポップアップ (§6.1) に出す。
 */
/** 1 つの既知話者への類似スコア (cos)。 */
export interface SpeakerCandidate {
  speaker: string;
  score: number;
}

export interface ClusterMapping {
  /** 自動クラスタ label (`SPEAKER_00` 形式)。 */
  cluster: string;
  /** 既定で対応づく既知話者名 (Hungarian)。null = τ未満 (新規話者扱い)。 */
  speaker: string | null;
  /** 既定割当先への類似スコア (cos)。 */
  score: number;
  /** 全既知話者へのスコア (降順)。選択を変えたとき表示を更新する用。 */
  scores: SpeakerCandidate[];
}

/** 話者。色は固定パレットから循環割当。 */
export interface Speaker {
  name: string;
  color: string;
}

/** 波形ピーク (min/max ペア)。BPS バケット/秒で事前計算。 */
export interface Peaks {
  min: Float32Array;
  max: Float32Array;
  /** バケット解像度 (バケット/秒) */
  bps: number;
}

/** デコード済み音声。 */
export interface DecodedAudio {
  duration: number;
  sampleRate: number;
  peaks: Peaks;
}
