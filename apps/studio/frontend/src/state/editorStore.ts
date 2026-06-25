import { create } from "zustand";
import { splitSegment } from "../domain/segment.ts";
import {
  compactSpeakerNames,
  deriveSpeakerOrder,
  nextSpeakerName,
  withRenamedSpeaker,
} from "../domain/speaker.ts";
import { markConfirmed, markEdited } from "../domain/status.ts";
import type { Recommendation, Segment, Suspicion } from "../domain/types.ts";
import { useEditOpsStore } from "./editOpsStore.ts";

/** undo/redo の単位スナップショット。 */
interface Snapshot {
  segments: Segment[];
  speakers: string[];
  selectedIds: string[];
  activeSpeaker: string | null;
}

const HISTORY_LIMIT = 100;

export function newId(): string {
  return crypto.randomUUID();
}

interface EditorState extends Snapshot {
  /** RTTM 書き出し時の識別子。 */
  fileId: string;
  past: Snapshot[];
  future: Snapshot[];

  importSegments(segments: Segment[], fileId?: string | null): void;
  setFileId(fileId: string): void;

  // 選択
  selectSingle(id: string | null): void;
  toggleSelect(id: string): void;
  setSelection(ids: string[]): void;
  addToSelection(ids: string[]): void;
  clearSelection(): void;
  setActiveSpeaker(name: string | null): void;

  // 編集 (履歴あり)
  /** ドラッグ開始時に1度だけ呼び、現状を past に積む。 */
  beginEdit(): void;
  /** resize ドラッグ開始。beginEdit + resize カウント。 */
  beginResize(): void;
  /** ドラッグ中のライブ更新 (履歴を積まない)。 */
  applyLive(segments: Segment[]): void;
  addSegment(seg: Segment): void;
  deleteSelected(): void;
  deleteSegment(id: string): void;
  splitAt(id: string, t: number): void;
  undo(): void;
  redo(): void;

  // 話者
  addSpeaker(): void;
  /** 話者とその区間を削除し、SPEAKER_NN を詰める (履歴あり)。 */
  removeSpeaker(name: string): void;
  /** activeSpeaker を name にし、選択があれば一括割当 (履歴あり)。 */
  pickSpeaker(name: string): void;
  setSegmentSpeaker(id: string, name: string): void;

  // 検証状態 (アノテーションモードの品質保証)
  /** 指定 id 群を confirmed にする (履歴あり)。 */
  confirmIds(ids: string[]): void;
  /** 単一セグメントの status を設定 (履歴あり)。 */
  setSegmentStatus(id: string, status: Segment["status"]): void;
  /** 話者をリネーム (全区間 + 順序 + active を更新, 履歴あり)。衝突/空は no-op。 */
  renameSpeaker(oldName: string, newName: string): void;
  /**
   * 一括対応 (§6.1): 複数の自動クラスタを既知話者名へ一度にリネーム (1履歴)。
   * status は変えない (個別検証は別途必要、QA ゲートを迂回しないため)。
   */
  applySpeakerMapping(pairs: { from: string; to: string }[]): void;
  /**
   * 編集追従: 再計算した怪しさ/レコメンドを id 一致の segment に反映する (履歴なし)。
   * geometry を変えないので followEdits の再発火ループは起きない。null は既存値を保持。
   */
  applySignals(
    patches: { id: string; suspicion: Suspicion | null; recommendation: Recommendation | null }[],
  ): void;
}

function snapshotOf(s: Snapshot): Snapshot {
  return {
    segments: s.segments,
    speakers: s.speakers,
    selectedIds: s.selectedIds,
    activeSpeaker: s.activeSpeaker,
  };
}

export const useEditorStore = create<EditorState>((set, get) => ({
  segments: [],
  speakers: [],
  selectedIds: [],
  activeSpeaker: null,
  fileId: "audio",
  past: [],
  future: [],

  importSegments(segments, fileId) {
    const speakers = deriveSpeakerOrder(segments);
    useEditOpsStore.getState().reset();
    set({
      segments,
      speakers,
      selectedIds: [],
      activeSpeaker: speakers[0] ?? null,
      past: [],
      future: [],
      ...(fileId ? { fileId } : {}),
    });
  },
  setFileId(fileId) {
    set({ fileId });
  },

  selectSingle(id) {
    set({ selectedIds: id ? [id] : [] });
  },
  toggleSelect(id) {
    const cur = get().selectedIds;
    set({
      selectedIds: cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id],
    });
  },
  setSelection(ids) {
    set({ selectedIds: [...ids] });
  },
  addToSelection(ids) {
    const merged = [...get().selectedIds];
    for (const id of ids) {
      if (!merged.includes(id)) merged.push(id);
    }
    set({ selectedIds: merged });
  },
  clearSelection() {
    set({ selectedIds: [] });
  },
  setActiveSpeaker(name) {
    set({ activeSpeaker: name });
  },

  beginEdit() {
    set((s) => ({
      past: [...s.past, snapshotOf(s)].slice(-HISTORY_LIMIT),
      future: [],
    }));
  },
  beginResize() {
    get().beginEdit();
    useEditOpsStore.getState().inc("resize");
  },
  applyLive(segments) {
    set({ segments });
  },
  addSegment(seg) {
    get().beginEdit();
    useEditOpsStore.getState().inc("create");
    set((s) => ({
      segments: [...s.segments, seg],
      speakers: deriveSpeakerOrder([...s.segments, seg], s.speakers),
      selectedIds: [seg.id],
    }));
  },
  deleteSelected() {
    const sel = new Set(get().selectedIds);
    if (sel.size === 0) return;
    get().beginEdit();
    useEditOpsStore.getState().inc("del");
    set((s) => ({
      segments: s.segments.filter((seg) => !sel.has(seg.id)),
      selectedIds: [],
    }));
  },
  deleteSegment(id) {
    get().beginEdit();
    useEditOpsStore.getState().inc("del");
    set((s) => ({
      segments: s.segments.filter((seg) => seg.id !== id),
      selectedIds: s.selectedIds.filter((x) => x !== id),
    }));
  },
  splitAt(id, t) {
    const seg = get().segments.find((s) => s.id === id);
    if (!seg) return;
    const pair = splitSegment(seg, t, newId());
    if (!pair) return;
    get().beginEdit();
    useEditOpsStore.getState().inc("split");
    set((s) => ({
      segments: s.segments.flatMap((x) => (x.id === id ? pair : [x])),
      selectedIds: [pair[0].id],
    }));
  },

  addSpeaker() {
    set((s) => {
      const name = nextSpeakerName(s.speakers);
      return { speakers: [...s.speakers, name], activeSpeaker: name };
    });
  },
  removeSpeaker(name) {
    if (!get().speakers.includes(name)) return;
    get().beginEdit();
    set((s) => {
      const removedIds = new Set(
        s.segments.filter((seg) => seg.speaker === name).map((seg) => seg.id),
      );
      const segments0 = s.segments.filter((seg) => seg.speaker !== name);
      const speakers0 = s.speakers.filter((n) => n !== name);
      const { segments, speakers, map } = compactSpeakerNames(segments0, speakers0);
      // active を追従: 削除対象なら先頭へ、リネームされたら新名へ。
      const renamedActive =
        s.activeSpeaker === name ? null : (map.get(s.activeSpeaker ?? "") ?? s.activeSpeaker);
      const activeSpeaker =
        renamedActive && speakers.includes(renamedActive) ? renamedActive : (speakers[0] ?? null);
      return {
        segments,
        speakers,
        activeSpeaker,
        selectedIds: s.selectedIds.filter((id) => !removedIds.has(id)),
      };
    });
  },
  pickSpeaker(name) {
    const sel = new Set(get().selectedIds);
    if (sel.size === 0) {
      set({ activeSpeaker: name });
      return;
    }
    get().beginEdit();
    useEditOpsStore.getState().inc("reassign");
    set((s) => {
      const segments = s.segments.map((seg) =>
        sel.has(seg.id) ? markEdited({ ...seg, speaker: name }) : seg,
      );
      return {
        segments,
        speakers: deriveSpeakerOrder(segments, s.speakers),
        activeSpeaker: name,
      };
    });
  },
  setSegmentSpeaker(id, name) {
    get().beginEdit();
    useEditOpsStore.getState().inc("reassign");
    set((s) => {
      const segments = s.segments.map((seg) =>
        seg.id === id ? markEdited({ ...seg, speaker: name }) : seg,
      );
      return { segments, speakers: deriveSpeakerOrder(segments, s.speakers) };
    });
  },
  confirmIds(ids) {
    const set_ = new Set(ids);
    if (set_.size === 0) return;
    get().beginEdit();
    set((s) => ({
      segments: s.segments.map((seg) => (set_.has(seg.id) ? markConfirmed(seg) : seg)),
    }));
  },
  setSegmentStatus(id, status) {
    get().beginEdit();
    set((s) => ({
      segments: s.segments.map((seg) => (seg.id === id ? { ...seg, status } : seg)),
    }));
  },
  renameSpeaker(oldName, newName) {
    const r = withRenamedSpeaker(get().segments, get().speakers, oldName, newName);
    if (!r) return;
    get().beginEdit();
    set((s) => ({
      ...r,
      activeSpeaker: s.activeSpeaker === oldName ? newName.trim() : s.activeSpeaker,
    }));
  },
  applySpeakerMapping(pairs) {
    const map = new Map<string, string>();
    for (const { from, to } of pairs) {
      const name = to.trim();
      if (name && name !== from) map.set(from, name);
    }
    if (map.size === 0) return;
    const rename = (n: string): string => map.get(n) ?? n;
    // 埋め込み済みの候補/怪しさラベル (SPEAKER_xx) も一括対応に追従させる
    // (候補集合 = 現在の話者ライン。一括対応は 1対1 リネームなので翻訳できる)。
    const renameSeg = (seg: Segment): Segment => ({
      ...seg,
      speaker: rename(seg.speaker),
      ...(seg.recommendation
        ? {
            recommendation: {
              ...seg.recommendation,
              candidates: seg.recommendation.candidates.map((c) => ({
                ...c,
                cluster: rename(c.cluster),
              })),
            },
          }
        : {}),
      ...(seg.suspicion?.nearest
        ? { suspicion: { ...seg.suspicion, nearest: rename(seg.suspicion.nearest) } }
        : {}),
    });
    get().beginEdit();
    set((s) => {
      const segments = s.segments.map(renameSeg);
      return {
        segments,
        speakers: deriveSpeakerOrder(segments, s.speakers.map(rename)),
        activeSpeaker: s.activeSpeaker ? rename(s.activeSpeaker) : s.activeSpeaker,
      };
    });
  },
  applySignals(patches) {
    if (patches.length === 0) return;
    const byId = new Map(patches.map((p) => [p.id, p]));
    set((s) => {
      let changed = false;
      const segments = s.segments.map((seg) => {
        const p = byId.get(seg.id);
        if (!p) return seg;
        // null は再計算不能 (リネーム済み等) → 既存値を保持。非 null は上書き (ok も反映)。
        const next = { ...seg };
        if (p.suspicion !== null) next.suspicion = p.suspicion;
        if (p.recommendation !== null) next.recommendation = p.recommendation;
        if (next.suspicion !== seg.suspicion || next.recommendation !== seg.recommendation) {
          changed = true;
          return next;
        }
        return seg;
      });
      return changed ? { segments } : s;
    });
  },
  undo() {
    set((s) => {
      const prev = s.past.at(-1);
      if (!prev) return s;
      return {
        ...prev,
        past: s.past.slice(0, -1),
        future: [...s.future, snapshotOf(s)],
      };
    });
  },
  redo() {
    set((s) => {
      const next = s.future.at(-1);
      if (!next) return s;
      return {
        ...next,
        past: [...s.past, snapshotOf(s)],
        future: s.future.slice(0, -1),
      };
    });
  },
}));
