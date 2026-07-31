// サイドカー JSON (<fileId>.voxmap.json) の生成と読み込み。RTTM は標準のまま保ち、
// 来歴と QA サマリをここに分離する。下流で「モデル出力そのまま」を監査できるのが狙い。
//
// 設計方針:
//   - 「完成」は flippable なフラグで自己申告させない。complete は segments から導出する
//     (auto が1件も無いこと)。途中保存と完成版は同じ1スキーマで、中身 (auto の有無) が違うだけ。
//   - integrity ハッシュで casual な手編集を検知する (tamper-evident であって tamper-proof ではない)。
//   - provenance を status に戻して読み込み再開できる (savepoint の往復)。
//   - audioName を保存して再開時に「この音声を読み込んでください」と案内できるようにする。
//     ブラウザは絶対パスを取得できないためファイル名のみ保存する。

import type { CatchSummary } from "./catch.ts";
import { countByStatus, provenanceToStatus, statusToProvenance } from "./status.ts";
import type { Segment } from "./types.ts";

const TOOL = "voxmap-studio";
/** 公開前 (repo 改名前) の studio が書き出していた tool 名。**読み込みのみ**受け付ける。 */
const LEGACY_TOOLS = ["speaker-diarization-studio"] as const;
/** 読み込みで受け付ける tool 名 (書き出しは常に TOOL)。通知の条件表示にも使う。 */
export const ACCEPTED_TOOLS: readonly string[] = [TOOL, ...LEGACY_TOOLS];
// v2: summary.cost (作業コスト計測) を追加。parseSidecar は cost 欠落を許容 (v1 互換)。
// v3: createdAt (初回セッション開始時刻) を追加。再開時に引き継ぎ、exportedAt との差で
//     日跨ぎ込みの総スパンを出せる。parseSidecar は欠落を許容 (v1/v2 互換)。
const SCHEMA_VERSION = 3;
const HASH_ALGO = "fnv1a-32";

/** FNV-1a 32bit。改変検知用の軽量ハッシュ (暗号強度は不要)。 */
function fnv1a(input: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}

interface SidecarSegment {
  start: number;
  end: number;
  speaker: string;
  provenance: string;
}

/** segments + fileId の正準表現からハッシュを計算する。出力/読み込みで同一になるよう丸め済み値を使う。 */
function integrityHash(fileId: string, segments: SidecarSegment[]): string {
  const canonical = segments
    .map((s) => `${s.start.toFixed(3)}|${s.end.toFixed(3)}|${s.speaker}|${s.provenance}`)
    .join("\n");
  return fnv1a(`${fileId}\n${canonical}`);
}

export interface SidecarInput {
  fileId: string;
  /** 音声/動画ファイル名 (拡張子込み)。再開時の読み込み案内に使う。
   *  ブラウザは絶対パスを取得できないためファイル名のみ保存する。 */
  audioName?: string;
  mode: string;
  segments: Segment[];
  percentHeard: number;
  catch: CatchSummary;
  /** 書き出し時刻 (ISO)。呼び出し側で new Date().toISOString()。省略可。 */
  exportedAt?: string;
  /** 初回セッション開始時刻 (ISO)。再開時は読み込んだ JSON の値を引き継ぐ。省略可。 */
  createdAt?: string;
  /** 作業コスト計測 (§4)。途中保存・完成版どちらにも記録する。省略可 (計測なし)。 */
  cost?: SidecarCost;
}

/** 編集操作の内訳。 */
export interface EditOpsDetail {
  reassign: number;
  resize: number;
  split: number;
  create: number;
  del: number;
}

/** 1セッションの作業コスト (導出値ではなく計測値)。 */
export interface SidecarCost {
  /** idle を除いたアクティブ作業秒。 */
  activeSec: number;
  /** 参考: ロード〜書き出しの実時間 (秒)。 */
  wallSec: number;
  /** 音声長 (秒)。activeSec / (audioSec/60) で sec/audio-min を出す。 */
  audioSec: number;
  /** 編集操作の合計。 */
  editOps: number;
  /** 編集操作の内訳。 */
  editOpsDetail: EditOpsDetail;
}

export interface Sidecar {
  schemaVersion: number;
  tool: string;
  fileId: string;
  audioName?: string;
  mode: string;
  exportedAt?: string;
  createdAt?: string;
  integrity: { algo: string; hash: string };
  summary: {
    segmentCount: number;
    byStatus: Record<string, number>;
    /** segments から導出 (auto が0件)。宣言ではなく計算値。 */
    complete: boolean;
    percentHeard: number;
    catchTrials: CatchSummary;
    /** 作業コスト計測 (§4)。計測なしのときは欠落。 */
    cost?: SidecarCost;
  };
  segments: SidecarSegment[];
}

/** コスト値を丸める (activeSec/wallSec は整数秒、audioSec は小数1桁)。 */
function roundCost(c: SidecarCost): SidecarCost {
  return {
    activeSec: Math.round(c.activeSec),
    wallSec: Math.round(c.wallSec),
    audioSec: Math.round(c.audioSec * 10) / 10,
    editOps: c.editOps,
    editOpsDetail: { ...c.editOpsDetail },
  };
}

export function buildSidecar(input: SidecarInput): Sidecar {
  const sorted = [...input.segments].sort((a, b) => a.start - b.start);
  const byStatus = countByStatus(sorted);
  const segments: SidecarSegment[] = sorted.map((s) => ({
    start: Math.round(s.start * 1000) / 1000,
    end: Math.round(s.end * 1000) / 1000,
    speaker: s.speaker,
    provenance: statusToProvenance(s.status),
  }));
  return {
    schemaVersion: SCHEMA_VERSION,
    tool: TOOL,
    fileId: input.fileId,
    ...(input.audioName ? { audioName: input.audioName } : {}),
    mode: input.mode,
    ...(input.exportedAt ? { exportedAt: input.exportedAt } : {}),
    ...(input.createdAt ? { createdAt: input.createdAt } : {}),
    integrity: { algo: HASH_ALGO, hash: integrityHash(input.fileId, segments) },
    summary: {
      segmentCount: segments.length,
      byStatus,
      complete: byStatus.auto === 0,
      percentHeard: Math.round(input.percentHeard * 1000) / 1000,
      catchTrials: input.catch,
      ...(input.cost ? { cost: roundCost(input.cost) } : {}),
    },
    segments,
  };
}

export function serializeSidecar(input: SidecarInput): string {
  return JSON.stringify(buildSidecar(input), null, 2);
}

export interface ParsedSidecar {
  fileId: string;
  /** 保存時の音声/動画ファイル名。読み込み未済みなら通知に使う。 */
  audioName?: string;
  segments: Segment[];
  /** auto が0件か (= 完成品質)。 */
  complete: boolean;
  /** integrity ハッシュが一致しない (= 手編集の疑い)。 */
  tampered: boolean;
  /** 保存済み作業コスト。再開時に activeSec / editOps を積み増す元。欠落時 undefined。 */
  cost?: SidecarCost;
  /** 初回セッション開始時刻 (ISO)。再開時に引き継ぐ。欠落時 undefined。 */
  createdAt?: string;
}

/** 読み込みを拒否した理由。呼び出し側 (loadFiles) が「なぜ弾いたか」を通知するために使う。 */
export type SidecarReject =
  | { reason: "not-json" }
  | { reason: "not-object" }
  /** tool が対応名でない。tool = 実際に入っていた値 (欠落・非文字列なら null)。 */
  | { reason: "tool-mismatch"; tool: string | null }
  | { reason: "segments-not-array" };

export type SidecarRead =
  | { ok: true; sidecar: ParsedSidecar }
  | { ok: false; reject: SidecarReject };

/**
 * voxmap.json を読み込んで編集状態を復元する (savepoint 再開)。
 * provenance → status に戻し、integrity を再計算して改変を検知する。
 * voxmap.json でなければ拒否理由を返す (呼び出し側が通知に使う)。
 *
 * tool は現行名と旧名 (ACCEPTED_TOOLS) を受け付ける。integrity ハッシュは fileId + segments
 * のみから計算し tool を含まないため、旧名 json でも tampered にはならない。
 */
export function readSidecar(text: string): SidecarRead {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return { ok: false, reject: { reason: "not-json" } };
  }
  if (typeof data !== "object" || data === null) {
    return { ok: false, reject: { reason: "not-object" } };
  }
  const d = data as Partial<Sidecar>;
  if (typeof d.tool !== "string" || !ACCEPTED_TOOLS.includes(d.tool)) {
    return {
      ok: false,
      reject: { reason: "tool-mismatch", tool: typeof d.tool === "string" ? d.tool : null },
    };
  }
  if (!Array.isArray(d.segments)) {
    return { ok: false, reject: { reason: "segments-not-array" } };
  }

  const fileId = typeof d.fileId === "string" ? d.fileId : "audio";
  const audioName = typeof d.audioName === "string" ? d.audioName : undefined;
  const raw: SidecarSegment[] = d.segments.map((s) => ({
    start: Number(s.start),
    end: Number(s.end),
    speaker: String(s.speaker),
    provenance: String(s.provenance),
  }));

  const segments: Segment[] = raw.map((s, i) => ({
    id: `sidecar-${i}`,
    start: s.start,
    end: s.end,
    speaker: s.speaker,
    status: provenanceToStatus(s.provenance),
  }));

  const expected = d.integrity?.hash;
  const actual = integrityHash(fileId, raw);
  const tampered = typeof expected === "string" ? expected !== actual : true;
  const complete = segments.every((s) => s.status !== "auto");

  const cost = parseCost(d.summary?.cost);
  const createdAt = typeof d.createdAt === "string" ? d.createdAt : undefined;

  return {
    ok: true,
    sidecar: {
      fileId,
      ...(audioName ? { audioName } : {}),
      segments,
      complete,
      tampered,
      ...(cost ? { cost } : {}),
      ...(createdAt ? { createdAt } : {}),
    },
  };
}

/**
 * readSidecar の薄いラッパ。拒否理由が不要な呼び出し側 (autosave 復元など) 用。
 * voxmap.json でなければ null。
 */
export function parseSidecar(text: string): ParsedSidecar | null {
  const read = readSidecar(text);
  return read.ok ? read.sidecar : null;
}

/** summary.cost を検証して取り出す。型不正・欠落は undefined。 */
function parseCost(c: unknown): SidecarCost | undefined {
  if (typeof c !== "object" || c === null) return undefined;
  const o = c as Partial<SidecarCost>;
  const d = o.editOpsDetail;
  if (typeof o.activeSec !== "number" || typeof d !== "object" || d === null) return undefined;
  return {
    activeSec: Number(o.activeSec) || 0,
    wallSec: Number(o.wallSec) || 0,
    audioSec: Number(o.audioSec) || 0,
    editOps: Number(o.editOps) || 0,
    editOpsDetail: {
      reassign: Number(d.reassign) || 0,
      resize: Number(d.resize) || 0,
      split: Number(d.split) || 0,
      create: Number(d.create) || 0,
      del: Number(d.del) || 0,
    },
  };
}
