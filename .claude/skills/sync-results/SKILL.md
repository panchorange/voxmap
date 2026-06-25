---
name: sync-results
description: 単一の <kind>/<theme>/<id>/<subdir>/ (subdir 既定=results) を GCS (gs://voxmap/) と upload / download / list で同期する。experiment-run / profile-run から呼ばれるほか、ユーザーが手動で同期したいときにも使う。
---

# sync-results

`scripts/sync_results.py` (= `gcloud storage rsync --recursive` の薄いラッパー) で、ローカル
`<kind>/<theme>/<id>/<subdir>/` と GCS `gs://voxmap/<kind>/<theme>/<id>/<subdir>/` を同期する。
パス規約は `.claude/rules/gcs-layout.md` に従う (ローカル構造を GCS にミラー)。
**ファイルの内容比較や上書きの判断は gcloud に任せる**。

## いつ起動するか

- **`experiment-run` / `profile-run` から呼ばれる** (結果アップロード時 / GCS list取得時)
- ローカル結果を消してしまい、GCS から復元したいとき
- 手動で1件だけ upload / download したいとき
- 一括 upload / download (`upload-all`, `download-all`)

`sync-check` で不整合を**検知**したあと、実際の修正に使う。

## 同期対象 (`--subdir`): results 以外も検討する

既定は `results/` (再生成可能な集計結果)。だが **upload 前に、実験ディレクトリへ
「git 管理外 かつ 再生成不可」なデータが results 以外に無いか確認し、あればユーザーに別途
up を提案する**。代表例:

- annotation テーマの `sidecars/` (人手アノテ成果物。gitignore 済みなら **GCS が唯一の
  バックアップ**になるので必ず提案する)

提案が受け入れられたら、results とは**別ラン**で `--subdir <name>` を回す (results は既定の
ままなので experiment-run / profile-run の呼び出しは無改修):

```bash
uv run python scripts/sync_results.py upload experiments/<theme>/<id> --subdir sidecars
```

## 手順

1. **引数確認** (足りなければユーザーに聞く):
   - 操作: `upload` / `download` / `list` / `upload-all` / `download-all`
   - 対象: `<kind>/<theme>/<id>` (kind ∈ experiments / profiles / analysis)
   - `--subdir`: 既定 `results`。上の提案を受けたら `sidecars` 等を指定

2. **認証チェック**: script 側で `gcloud auth list --filter=status:ACTIVE` を自動実行。
   失敗時は exit 1。`gcloud auth login` を促す案内をそのまま伝える

3. **実行**:
   ```bash
   uv run python scripts/sync_results.py upload   <kind>/<theme>/<id>                 # results (既定)
   uv run python scripts/sync_results.py upload   <kind>/<theme>/<id> --subdir sidecars
   uv run python scripts/sync_results.py download <kind>/<theme>/<id> [--subdir <name>]
   uv run python scripts/sync_results.py list     <kind>/<theme>/<id> [--subdir <name>]
   uv run python scripts/sync_results.py upload-all   [--kind experiments|profiles|analysis] [--subdir <name>]
   uv run python scripts/sync_results.py download-all [--kind experiments|profiles|analysis] [--subdir <name>]
   ```

4. **結果をユーザーに提示**:
   - upload / download: `OK: uploaded → gs://...` / `OK: downloaded ← gs://...` を確認
   - 失敗時 (rc != 0): エラーをそのまま転記し、再試行か手動 gcloud を促す
   - `<subdir>/` が空の upload は warning で skip (失敗ではない)
   - list: 出力をそのままユーザーに渡す

## 他の skill からの呼び出し方

`experiment-run` / `profile-run` からは以下のように呼ぶ (subdir 省略=results):

- **アップロード**: `Skill(skill="sync-results", args="upload experiments/<theme>/<id>")`
- **GCS list (PR body 用)**: `Skill(skill="sync-results", args="list experiments/<theme>/<id>")`

呼び出し側は失敗を吸収する (gcloud 失敗で notes 更新まで止めない)。

## やってはいけないこと

- ローカルを勝手に削除しない (download は rsync で追加・更新のみ)
- GCS 側を `--delete-unmatched-destination-objects` で削除しない (デフォルト off)
- `kind` / `id` / `subdir` を勝手に推測しない (引数で明示。subdir は単一フォルダ名のみ=script が検証)
- 認証情報を log に流さない (gcloud の出力はそのまま、加工せず転記)

## 参考

- 実装本体: `scripts/sync_results.py`
- パス規約: `.claude/rules/gcs-layout.md`
- 関連 skill: `sync-check` (整合性検査), `experiment-run` / `profile-run` (呼び出し元)
- GCS: `gs://voxmap/<kind>/<theme>/<id>/<subdir>/` (subdir 既定=results。sidecars 等は別途 up)
