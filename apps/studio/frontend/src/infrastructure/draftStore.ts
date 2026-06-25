// autosave のドラフト永続化 (IndexedDB)。リロード・クラッシュで作業が消えないための保険。
// - 正式なバックアップは「途中保存」(ファイル書き出し) が担う。ここは裏方の自動保存。
// - 保存先は IndexedDB (idb-keyval ラッパー)。localStorage より大容量・非同期で autosave 向き。
// - fileId 単位で1ドラフト。直近 LIMIT 件だけ残し、古いものは保存時に削除 (LRU)。
// - 音声バイナリは保存しない (大きすぎ + パス取得不可)。状態 (sidecar JSON) のみ。復元時は
//   音声を再ロード案内する (ファイル復元と同じ制約)。

import { del, get, keys, set } from "idb-keyval";

/** 同時に保持するドラフトの上限。これを超えると古いものから削除する。 */
export const DRAFT_LIMIT = 5;

const PREFIX = "draft:";

export interface DraftRecord {
  /** RTTM 識別子。ドラフトのキー。 */
  fileId: string;
  /** 保存時の音声ファイル名 (復元時の再ロード案内に使う)。 */
  audioName?: string;
  /**
   * File System Access のファイルハンドル (対応ブラウザのみ)。IndexedDB は構造化複製で
   * ハンドルをそのまま保存できる。再開時に1クリックで音声を自動復元する元。
   */
  audioHandle?: FileSystemFileHandle;
  /** serializeSidecar の結果 (voxmap.json と同じ文字列)。 */
  sidecar: string;
  /** 保存時刻 (epoch ms)。LRU の新旧判定と「○分前」表示に使う。呼び出し側から注入。 */
  savedAt: number;
}

function keyOf(fileId: string): string {
  return PREFIX + fileId;
}

/**
 * LRU で削除すべきレコードを選ぶ (純粋関数)。savedAt が新しい順に limit 件残し、
 * あふれた古い分を返す。IndexedDB に触れないので単体テストできる。
 */
export function selectEvictions(records: DraftRecord[], limit: number): DraftRecord[] {
  if (records.length <= limit) return [];
  const byNewest = [...records].sort((a, b) => b.savedAt - a.savedAt);
  return byNewest.slice(limit);
}

/** ドラフトを保存し、上限を超えた古いドラフトを削除する。 */
export async function saveDraft(rec: DraftRecord): Promise<void> {
  await set(keyOf(rec.fileId), rec);
  const all = await listDrafts();
  for (const old of selectEvictions(all, DRAFT_LIMIT)) {
    await del(keyOf(old.fileId));
  }
}

/** fileId のドラフトを取り出す。無ければ undefined。 */
export async function loadDraft(fileId: string): Promise<DraftRecord | undefined> {
  return await get<DraftRecord>(keyOf(fileId));
}

/** 全ドラフトを savedAt の新しい順で返す。 */
export async function listDrafts(): Promise<DraftRecord[]> {
  const ks = (await keys()).filter(
    (k): k is string => typeof k === "string" && k.startsWith(PREFIX),
  );
  const recs = await Promise.all(ks.map((k) => get<DraftRecord>(k)));
  return recs
    .filter((r): r is DraftRecord => r !== undefined)
    .sort((a, b) => b.savedAt - a.savedAt);
}

/** fileId のドラフトを削除する (完成書き出し時・手動破棄時)。 */
export async function deleteDraft(fileId: string): Promise<void> {
  await del(keyOf(fileId));
}
