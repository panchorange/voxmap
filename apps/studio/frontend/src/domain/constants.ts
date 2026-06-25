// ドメイン定数 (仕様: docs/design/annotation-tool/機能一覧.md)

/** 最小区間長 (秒) */
export const MIN_SEG = 0.02;

/** 波形ピークのバケット解像度 (バケット/秒) */
export const BPS = 500;

/** 時間ルーラーの高さ (px) */
export const RULER_H = 22;

/** 波形ストリップ (ルーラー + 波形) の高さ (px)。スクロールしても上部に固定で常に見える */
export const STRIP_H = 132;

/** 話者レーン1本の高さ (px, 固定)。話者数ぶん縦に積み、はみ出たら下のレーン領域だけスクロール */
export const LANE_H = 52;

/** 同時に表示するレーン数の上限。これを超えると波形は固定のままレーン領域だけ縦スクロール。
 *  話者が多い (over-segmentation 含む) と全体が縦に伸びすぎるため低めに。AMI は基本4話者。 */
export const MAX_VISIBLE_LANES = 4;

/** 区間の端とみなすヒット範囲 (px) */
export const EDGE_PX = 6;

/** pps (pixels per second) の上限 */
export const PPS_MAX = 5000;

/** pps の下限 = フィット幅の何倍か */
export const PPS_MIN_FIT_RATIO = 0.6;

/** ズーム1ステップの倍率 (ボタン) */
export const ZOOM_STEP = 1.5;
