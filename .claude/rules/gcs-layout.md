# GCS レイアウト (結果データの保管)

`results/` (容量が大きく git に載せない実測結果) のバックアップ先は GCS。
**ローカル repo の構造をそのまま GCS にミラーする**。設計/notes は git・Obsidian 側。

## パス規約

- バケット: `gs://voxmap`
- **`gs://voxmap/<kind>/<theme>/<id>/results/`** … ローカル `<kind>/<theme>/<id>/results/` と1:1
  - `<kind>` ∈ `experiments` / `profiles` / `analysis`
  - `<theme>` = `<テーマ日付>_<テーマ名>` (例: `2026-06-02_annotation-tools`)
  - `<id>` = `<日付>_<名前>` (例: `2026-06-15_c1c2c3-annotation-cost`)

例:
```
gs://voxmap/experiments/2026-06-02_annotation-tools/2026-06-15_c1c2c3-annotation-cost/results/
gs://voxmap/profiles/2026-05-27_ASR-diarization/2026-05-30_parakeet/results/
```

## 同期は必ず script (skill) 経由

パス規約を一箇所に集約するため、**手で `gsutil cp` / `gcloud storage cp` しない**。
`scripts/sync_results.py` (= `sync-results` skill) を使う。`<theme>/<id>` を渡せば
上記 URI を自動生成する。

```bash
# 単一 upload / download / list
uv run python scripts/sync_results.py upload   experiments/<theme>/<id>
uv run python scripts/sync_results.py download experiments/<theme>/<id>
uv run python scripts/sync_results.py list     experiments/<theme>/<id>
# 一括 (kind で絞り込み可)
uv run python scripts/sync_results.py upload-all --kind experiments
```

整合性チェックは `sync-check` skill (`scripts/sync_check.py`) が repo / Obsidian / `_index.md` /
GCS を突き合わせる。

## レガシー (テーマ未分離) の扱い

テーマ構造 (2026-06 頃) の導入前にアップした一部 id は、theme 階層なしで
`gs://voxmap/experiments/<id>/` に直接置かれている (例: `2026-05-07_pyannote31-pe/`)。
これは名残。**新規アップロードは必ず theme 分け**にする。既存のレガシーは無理に移動しない
(必要になったら別タスクで `gs://voxmap/experiments/<id>/` → `<theme>/<id>/` へ移行)。
