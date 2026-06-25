---
name: sync-check
description: repo (experiments/<id>/, profiles/<id>/) と Obsidian docs (docs/experiments/, docs/profiles/) と _index.md と GCS (gs://voxmap/) の整合性をチェックし、欠けているエントリ・未アップロードのデータを markdown レポートで提示する。同期忘れの検知に使う。
---

# sync-check

`scripts/sync_check.py` を呼び出し、以下の整合性を一括検査する。
**修正は自動でやらず、不整合の一覧と修正候補だけ提示する。**

検査対象:

1. repo dir (`experiments/<id>/` または `profiles/<id>/`) の有無
2. Obsidian docs (`docs/experiments/<id>.md` または `docs/profiles/<id>.md`) の有無
3. `_index.md` への wiki link 記載の有無
4. ローカル結果ファイルの有無 (experiments: `results/metrics.json` / profiles: `results/` 非空)
5. GCS (`gs://voxmap/<kind>/<theme>/<id>/results/`) の有無 — gcloud 未認証なら `-` で表示
   (パス規約は `.claude/rules/gcs-layout.md`。theme 階層なしの flat な GCS entry はレガシー)

## いつ起動するか

- 「実験/計測の一覧と Obsidian / GCS のズレを確認したい」
- 実験/計測の追加・削除・リネーム後の確認
- 定期的な棚卸し (週1回など)
- `experiments/<id>/results/metrics.json` が無いように見えるが、消したのか走らせ忘れたのか判断したいとき

## 手順

1. **引数確認** (足りなければユーザーに聞く):
   - `kind`: `experiments` / `profiles` / `all` (省略時は `all`)

2. **`scripts/sync_check.py` を実行**:
   ```bash
   uv run python scripts/sync_check.py [--kind experiments|profiles|all]
   ```
   - 不整合があると exit 1。ユーザーへの提示には支障ないので exit code は無視してよい

3. **結果をユーザーに提示**:
   - スクリプトが markdown 表 + 「修正候補」リストを出すので、そのまま貼り付ける
   - **追加で次の行動を促す**:
     - GCS への upload が漏れているもの: `sync-results upload <kind>/<id>` を提案
     - GCS にあるが local に無いもの: `sync-results download <kind>/<id>` を提案 (削除済みの可能性も確認)
     - docs/_index.md の記載漏れ: 該当ファイルを開く案内
     - ローカル結果ファイル欠損: 再実行 (`experiment-run` / `profile-run`) or GCS から download
   - **どの修正を実行するかはユーザーが選ぶ**。自動で sync を走らせない

4. **gcloud が使えない場合**:
   - script が `注意:` 警告を出すので、そのまま伝える
   - 「GCS 列は確認できなかった」と明示し、`gcloud auth login` を促す

## やってはいけないこと

- 不整合を検出しても**自動で修正しない** (rename / upload / commit)
- `docs/.../_index.md` を勝手に書き換えない (どの行に挿入すべきかは人間判断)
- 「これは消した方がいい」など断定しない (削除は不可逆)
- gcloud 失敗で skill 全体を止めない (検査の他項目だけでも結果を出す)

## 参考

- 実装本体: `scripts/sync_check.py`
- パス規約: `.claude/rules/gcs-layout.md` (results 以外に sidecars 等を上げる運用もここ)
- 関連 skill: `sync-results` (実際の upload / download), `experiment-run` / `profile-run` (走らせて結果を残す)
- GCS バケット: `gs://voxmap/<kind>/<theme>/<id>/results/`
- Makefile target: `make sync-check`
