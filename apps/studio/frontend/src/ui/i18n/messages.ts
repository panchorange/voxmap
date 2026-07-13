// UI 文言の単一ソース。**1キーにつき ja / en を必ず並べて持つ** ことで、
// 「この文言は日英でどう対応しているか」がこのファイルだけで一望できる。
// 新しい文言を足すときは必ず ja と en の両方を埋めること (型で強制される)。
//
// プレースホルダは `{name}` 形式。`t("key", { name: x })` で置換する (t.ts)。
// 文言は features / 画面ごとにグルーピング (キー接頭辞 = だいたいの所在)。

export const LANGS = [
  { id: "ja", label: "日本語" },
  { id: "en", label: "English" },
] as const;

export type Lang = (typeof LANGS)[number]["id"];

export function isLang(value: string | null): value is Lang {
  return LANGS.some((l) => l.id === value);
}

// 1 文言 = { ja, en }。両方必須 (片方だけだと型エラー)。
type Msg = { ja: string; en: string };

export const MESSAGES = {
  // ---- 汎用 ----
  "common.close": { ja: "閉じる", en: "Close" },
  "common.justNow": { ja: "たった今", en: "just now" },
  "common.minutesAgo": { ja: "{n}分前", en: "{n} min ago" },
  "common.hoursAgo": { ja: "{n}時間前", en: "{n} h ago" },

  // ---- ヘッダー / ツールバー ----
  "header.badge.annotation": { ja: "アノテーション", en: "Annotation" },
  "header.audioVideo": { ja: "音声/動画", en: "Audio/Video" },
  "header.rttmJson": { ja: "RTTM/JSON", en: "RTTM/JSON" },
  "header.rttmJson.title": {
    ja: "RTTM または voxmap.json (途中保存) を読み込む",
    en: "Load RTTM or voxmap.json (savepoint)",
  },
  "header.speakerCount": { ja: "話者数", en: "Speakers" },
  "header.speakerCount.title": {
    ja: "話者数を指定 (AUTO は自動推定)",
    en: "Set number of speakers (AUTO = estimate)",
  },
  "header.speakerCount.range": { ja: "1〜{max} の整数", en: "integer 1–{max}" },
  "header.minDurationOn": { ja: "未満削除", en: "Drop <" },
  "header.minDurationOn.title": {
    ja: "これ未満の短い区間を削除する (OFF で無効化)",
    en: "Remove segments shorter than this (OFF disables it)",
  },
  "header.diarize": { ja: "話者分離", en: "Diarize" },
  "header.diarize.running": { ja: "分離中…", en: "Diarizing…" },
  "header.diarize.title": {
    ja: "話者分離を実行 (現在はスタブ)",
    en: "Run diarization (currently a stub)",
  },
  "header.diarize.invalid": {
    ja: "話者数は 1〜{max} の整数で入力してください",
    en: "Enter the number of speakers as an integer 1–{max}",
  },
  "header.savepoint": { ja: "途中保存", en: "Savepoint" },
  "header.savepoint.title": {
    ja: "voxmap.json で途中保存 (後で読み込んで再開できる)",
    en: "Save progress as voxmap.json (reload later to resume)",
  },
  "header.export": { ja: "書き出し", en: "Export" },
  "header.export.title.annotation": {
    ja: "完成版を書き出す (未検証が残るとブロック)",
    en: "Export the finished result (blocked while unverified remain)",
  },
  "header.export.title.viewer": { ja: "RTTM を書き出す", en: "Export RTTM" },

  // ---- ドロップゾーン ----
  "dropzone.hint": {
    ja: "ここにドロップ (音声 / 動画 / RTTM / voxmap.json)",
    en: "Drop here (audio / video / RTTM / voxmap.json)",
  },

  // ---- モード切替 ----
  "mode.viewer": { ja: "閲覧", en: "Viewer" },
  "mode.annotation": { ja: "アノテーション", en: "Annotation" },

  // ---- 保存ステータス ----
  "save.saving": { ja: "保存中…", en: "Saving…" },
  "save.error": { ja: "⚠ 保存に失敗", en: "⚠ Save failed" },
  "save.saved": { ja: "✓ 保存しました", en: "✓ Saved" },
  "save.savedAt": { ja: "✓ {time} に保存", en: "✓ Saved at {time}" },
  "save.autoSavedAt": { ja: "✓ {time} に自動保存", en: "✓ Auto-saved at {time}" },
  "save.title": {
    ja: "作業はブラウザに自動保存されます (Cmd/Ctrl+S で手動保存)",
    en: "Work is auto-saved in the browser (Cmd/Ctrl+S to save manually)",
  },

  // ---- 復元バナー (起動時の autosave 復元) ----
  "restore.prompt": {
    ja: "前回の自動保存があります ({fileId} / {ago})。復元しますか?",
    en: "An auto-save exists ({fileId} / {ago}). Restore it?",
  },
  "restore.withAudio": {
    ja: "（音声も自動で読み込みます）",
    en: " (audio will be loaded too)",
  },
  "restore.restore": { ja: "復元", en: "Restore" },
  "restore.discard": { ja: "破棄", en: "Discard" },

  // ---- 通知 (loadFiles の notify) ----
  "notice.autosaveSource": { ja: "自動保存", en: "auto-save" },
  "notice.restored": { ja: "自動保存を復元しました", en: "Restored from auto-save" },
  "notice.restoreAudioFailed": {
    ja: "音声の自動復元に失敗 — 「音声/動画」から読み込んでください",
    en: "Could not auto-restore audio — load it from “Audio/Video”",
  },
  "notice.loaded": {
    ja: "{source} を読み込みました — {notes}",
    en: "Loaded {source} — {notes}",
  },
  "notice.tampered": {
    ja: "⚠ integrity 不一致 (手編集の疑い)",
    en: "⚠ integrity mismatch (possibly hand-edited)",
  },
  "notice.complete": { ja: "完成 (auto 0件)", en: "complete (0 auto)" },
  "notice.draft": { ja: "途中保存 (未検証あり)", en: "savepoint (has unverified)" },
  "notice.audioMissingNamed": {
    ja: '音声未読み込み — "{audioName}" を「音声/動画」ボタンから読み込んでください',
    en: 'Audio not loaded — load "{audioName}" via the “Audio/Video” button',
  },
  "notice.audioMissing": {
    ja: "音声未読み込み — 「音声/動画」ボタンから読み込んでください",
    en: "Audio not loaded — load it via the “Audio/Video” button",
  },

  // ---- 自動分離エラー ----
  "diarize.failed": {
    ja: "自動分離に失敗しました: {msg} (backend が起動しているか確認してください: make studio-be-dev)",
    en: "Diarization failed: {msg} (check that the backend is running: make studio-be-dev)",
  },

  // ---- 分離オーバーレイ ----
  "overlay.diarizing": { ja: "話者分離中…", en: "Diarizing…" },
  "overlay.progress": {
    ja: "経過 {elapsed}s / 推定所要 約{estimate}s",
    en: "elapsed {elapsed}s / est. ~{estimate}s",
  },

  // ---- ファイルピッカー ----
  "picker.audioVideo": { ja: "音声 / 動画", en: "Audio / Video" },

  // ---- 区間リスト ----
  "seglist.empty": { ja: "区間がありません", en: "No segments" },
  "seglist.status.auto": { ja: "未検証", en: "Unverified" },
  "seglist.status.edited": { ja: "編集", en: "Edited" },
  "seglist.status.confirmed": { ja: "確認済", en: "Confirmed" },
  "seglist.status.confirmedTitle": { ja: "確認済み", en: "Confirmed" },
  "seglist.status.confirmTitle": {
    ja: "聴いてから確認する (再生済みなら確認、未再生なら再生)",
    en: "Listen, then confirm (confirms if already played, else plays)",
  },

  // ---- 一括バー ----
  "bulk.selectedCount": { ja: "{n}件選択中", en: "{n} selected" },
  "bulk.assignSpeaker": { ja: "話者を一括:", en: "Assign speaker:" },
  "bulk.selectPlaceholder": { ja: "選択…", en: "Select…" },
  "bulk.confirm": { ja: "確認 (C)", en: "Confirm (C)" },
  "bulk.confirm.title": {
    ja: "聴いた区間を確認済みにする (C)",
    en: "Mark listened segments as confirmed (C)",
  },
  "bulk.confirm.notHeard": {
    ja: "未再生のため確認できません。再生して聴いてから確認してください。",
    en: "Cannot confirm: not played yet. Play and listen first.",
  },
  "bulk.delete": { ja: "削除", en: "Delete" },
  "bulk.clear": { ja: "選択解除 (Esc)", en: "Clear (Esc)" },

  // ---- 話者チップ ----
  "chips.label.title": {
    ja: "クリック=選択/割当 · ダブルクリック or Enter=名前変更",
    en: "Click = select/assign · Double-click or Enter = rename",
  },
  "chips.remove.title": { ja: "{name} を削除", en: "Delete {name}" },
  "chips.removeConfirm": {
    ja: "{name} と {count}件の区間を削除します。よろしいですか?",
    en: "Delete {name} and {count} segment(s). Are you sure?",
  },
  "chips.add": { ja: "＋追加", en: "+ Add" },

  // ---- 候補話者パネル ----
  "candidate.playSegment.title": { ja: "このセグメントを再生", en: "Play this segment" },
  "candidate.segment": { ja: "▶ 区間", en: "▶ Segment" },
  "candidate.title": { ja: "候補話者", en: "Candidates" },
  "candidate.close.title": { ja: "閉じる (Esc)", en: "Close (Esc)" },
  "candidate.empty": {
    ja: "候補なし (自動分離の埋め込みがありません)",
    en: "No candidates (no diarization embeddings)",
  },
  "candidate.preview.title": { ja: "{cluster} を試聴", en: "Preview {cluster}" },
  "candidate.current.title": { ja: "現在の割当", en: "Current assignment" },
  "candidate.moveTo.title": { ja: "{cluster} へ移動", en: "Move to {cluster}" },
  "candidate.current": { ja: "現在", en: "current" },
  "candidate.novel.title": {
    ja: "どのラインにも該当しない → 新しい話者ラインへ",
    en: "Matches no line → create a new speaker line",
  },
  "candidate.novel": { ja: "＋ 新規話者 (どれでもない)", en: "+ New speaker (none of these)" },
  "candidate.recommended": { ja: "推奨", en: "recommended" },

  // ---- 話者対応づけダイアログ ----
  "mapping.title": { ja: "話者の対応づけ", en: "Map speakers" },
  "mapping.body": {
    ja: "自動分離の各話者を、既知話者 (ギャラリ) に対応づけます。 行ごとに変更でき、類似が低い (τ未満) 行は既定で「新規話者」です。 ▶ でその話者の声を試聴してから選べます。",
    en: "Map each diarized speaker to a known speaker (gallery). Each row is editable; low-similarity rows (below τ) default to “New speaker”. Use ▶ to preview a voice before choosing.",
  },
  "mapping.preview.cluster.title": {
    ja: "この話者の声を試聴 (代表セグメント)",
    en: "Preview this speaker (representative segment)",
  },
  "mapping.preview.speaker.title": {
    ja: "選択中の既知話者の声を試聴",
    en: "Preview the selected known speaker",
  },
  "mapping.novelOption": { ja: "新規話者 (対応なし)", en: "New speaker (no match)" },
  "mapping.score.novel": { ja: "新規", en: "new" },
  "mapping.score.similarity": { ja: "類似度 {score}", en: "similarity {score}" },
  "mapping.no": { ja: "いいえ (対応づけ不要)", en: "No (skip mapping)" },
  "mapping.yes": { ja: "はい (一括適用)", en: "Yes (apply all)" },

  // ---- 書き出しモーダル ----
  "export.title.draft": { ja: "途中保存", en: "Savepoint" },
  "export.title.final": { ja: "書き出し", en: "Export" },
  "export.body.draft": {
    ja: "途中保存は voxmap.json のみ。読み込めば status (確認状態) ごと再開できます。 完成RTTMは全区間を検証したときだけ書き出せます。",
    en: "A savepoint is voxmap.json only. Reload it to resume with statuses intact. The final RTTM can be exported only after all segments are verified.",
  },
  "export.body.draftUnverified": { ja: " (現在 未検証あり)", en: " (currently has unverified)" },
  "export.body.final": {
    ja: "RTTM は標準形式。voxmap.json に来歴 (auto / human_edited / human_confirmed) と QA サマリ・integrity ハッシュを記録します。",
    en: "RTTM is the standard format. voxmap.json records provenance (auto / human_edited / human_confirmed), a QA summary, and an integrity hash.",
  },
  "export.copied": { ja: "コピー済み", en: "Copied" },
  "export.copy": { ja: "表示中をコピー", en: "Copy shown" },
  "export.downloadBoth": { ja: "両方ダウンロード", en: "Download both" },
  "export.download": { ja: "ダウンロード", en: "Download" },

  // ---- 未検証ゲート (モーダル) ----
  "gate.title": { ja: "未検証の区間があります", en: "Unverified segments remain" },
  "gate.body": {
    ja: "未検証 (auto) の区間が {n} 件あります。 完成版は全区間を検証してからでないと書き出せません。各区間を聴いて 確認 (C) または編集してください。作業が途中なら「途中保存」で保存し、後で読み込んで再開できます。",
    en: "There are {n} unverified (auto) segment(s). The final result can be exported only after every segment is verified. Listen to each and Confirm (C) or edit it. If you are mid-way, use “Savepoint” to save and resume later.",
  },
  "gate.savepoint": { ja: "途中保存する", en: "Save a savepoint" },
  "gate.savepoint.title": {
    ja: "voxmap.json で途中保存 (後で再開できる)",
    en: "Save progress as voxmap.json (resume later)",
  },
  "gate.jump": { ja: "最初の未検証へ移動", en: "Go to first unverified" },

  // ---- 罠 (phantom) 警告モーダル ----
  "kept.title": { ja: "罠の区間を残しています", en: "Trap segments left in place" },
  "kept.body": {
    ja: "確認/編集して残した区間のうち {n} 件は、ツールが 無音区間に仕込んだ「偽の発話 (phantom)」です。これらは基本的に発話がない前提です。 本当に発話があったか聴き直してください。誤って残している場合は削除を。",
    en: "Of the segments you confirmed/edited, {n} are “phantom” utterances the tool planted in silent regions. These are assumed to have no speech. Re-listen to check whether speech is really there; delete any kept by mistake.",
  },
  "kept.review": { ja: "最初の罠を聴き直す", en: "Re-listen to first trap" },
  "kept.exportAnyway": { ja: "このまま書き出す", en: "Export anyway" },
  "kept.exportAnyway.title": {
    ja: "罠を残したまま書き出す (voxmap.json の kept に記録されます)",
    en: "Export with traps kept (recorded under kept in voxmap.json)",
  },

  // ---- 言語切替 ----
  "lang.label": { ja: "言語", en: "Language" },
} as const satisfies Record<string, Msg>;

export type MessageKey = keyof typeof MESSAGES;
