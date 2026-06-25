---
name: experiment-run
description: 既存の experiments/<theme>/<id>/ の run.py を走らせ、results/metrics.json から DER / RTF を取り出して notes.md・docs/experiments/<theme>/<id>.md・docs/experiments/<theme>/_index.md の結果テーブルを更新する。実験を「実行→記録」を一連で済ませたいときに起動。
---

# experiment-run

`experiments/<theme>/<id>/` 

`results/` は gitignore で消えうる前提なので、**数値を notes/docs に必ず転記する** のが
このskillの主目的。

## いつ起動するか

- 既存の実験ディレクトリを「走らせて結果を残す」とき
- run.py を再実行して数字を上書きしたいとき (実装変更後の再評価など)
- 過去に走らせた `metrics.json` から記録だけし直したいとき (`--no-run` 想定)

新規実験を **作成** したいだけなら `experiment-design` のほう。

## 手順

1. **引数確認** (足りなければユーザーに聞く):
   - 実験ID (`experiments/<id>/` の `<id>`)
   - 実行オプション (`--max-files N`, `--split test.mini` など smoke vs full)
   - 既に `results/metrics.json` があれば「再実行 / 既存を使う」を確認

2. **ブランチ確認 + 実行前 commit** (commit は提示のみ・自動でやらない):
   - `git branch --show-current` で現在のブランチが `exp/<id>` であることを確認する。
     違うブランチにいる場合は「`exp/<id>` に切り替えてから実行することを推奨します」と伝える
   - `git status` を確認し、`src/voxmap/`・`configs/`・`experiments/<id>/run.py`・`experiments/<id>/config.yaml` 等
     **評価対象コードに未 commit 変更があれば**、ユーザーに
     「実行前に commit してから走らせるか?」を**確認**する
   - 理由: `metrics.json` に記録される `git_commit` を clean なハッシュにしたい。
     後から `git diff <design_commit>..<result_commit>` で「設計時との実装差分」が追えるようにしたい
   - ユーザーが「commit する」と言ったら、対象ファイルと commit message 案を提示してから commit:
     ```
     update: experiments/<id> 実装 (run.py / config.yaml)
     ```
     実験 notes / docs はこの commit には含めない
   - notes/docs だけの変更や、再実行で何も変わっていない場合はこのステップをスキップ

3. **実行**:
   ```bash
   uv run python experiments/<id>/run.py [オプション]
   ```
   - 数時間級になる場合は `run_in_background: true` で投げて完了通知を待つ
   - 終了後 `experiments/<id>/results/metrics.json` の存在を確認
   - 失敗したら notes に「失敗ログ」セクションを追加してスタックトレース要点を残す

4. **metrics.json から抽出**:
   - `metrics.der_micro`, `metrics.der_macro`, `metrics.rtf`
   - `metrics.total_inference_seconds` (推論時間合計)
   - `metrics.total_audio_seconds` (総音声時間)
   - `metrics.n_files` (ファイル数)
   - `data_manifest` の長さとミーティング名からデータセット名を推定 (例: AMI test)
   - 話者数一致率: `per_file` の各 `n_speakers_predicted == n_speakers_reference` を集計 → `<一致数>/<総数> (XX%)`
   - `evaluation` セクション全体 (collar / skip_overlap / split / n_speakers)
   - `git_commit`, `completed_at`, `device`
   - ハードウェア詳細を以下のコマンドで取得する:
     ```bash
     # macOS (Apple Silicon)
     system_profiler SPHardwareDataType | grep -E "Model Name|Chip|Memory:"
     # CUDA (Linux / Windows WSL)
     nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
     uname -srm
     ```
   - `per_file` から DER 最悪 / 最良 meeting を1つずつピック (考察提案用)

5. **`experiments/<id>/notes.md` を更新**:
   - 「結果」テーブルの `—` を実数で置換。以下のフィールドを **必ず** 含める:
     - DER (micro), DER (macro), RTF
     - 推論時間 (s): `metrics.total_inference_seconds`
     - 話者数一致: `<一致数>/<総数> (XX%)` — per_file の n_speakers_predicted == n_speakers_reference を集計
   - 「データ」行を結果テーブルの直下に追記:
     ```
     データ: <データセット名> <split> — <n_files> files, <total_audio_seconds/3600:.1f>h
     ```
   - `実行: <git_commit_short> @ <completed_at> device=<device> hw=<hardware>` を記入
   - 散文は書かない。仮説・考察は docs/ 側のみ

6. **`docs/experiments/<id>.md` を更新**:
   - 「結果」テーブルに数値 + `実行: <git_commit_short> @ <completed_at>` を併記
   - 「考察」セクションには **観察事実のみ** bullet で1〜3個提案する (解釈・結論はユーザーが書く):
     - DER 最悪 / 最良 meeting
     - ベースラインとの差分の方向
     - 目立った per-file ばらつきがあれば
   - 「次にやること」セクションは **空欄のまま残す** (考察が未記入のため提案不可)

7. **`docs/experiments/<theme>/_index.md` のテーマ別ログ表を更新**:
   - 該当 `<日付> | <実験名>` 行の DER / RTF / 結果バッジを埋める
   - 行が無ければ追記
   - バッジ凡例: 🟢成功 / 🟡部分成功 / 🔴失敗 / 🟦基準 / ⏸保留
     - baseline初回は 🟦
     - 仮説確認系は DER改善幅で🟢/🟡/🔴を提案 (最終判断はユーザー)

8. **GCS に results をアップロード** (`sync-results` skill 経由):
   ```
   Skill(skill="sync-results", args="upload experiments/<id>")
   ```
   - 認証チェックと `gcloud storage rsync` は `sync-results` 側に任せる
   - 失敗した場合はスキップして注意だけ出す (upload 失敗でノート記録まで止めない)
   - upload 後は GCS の URL `gs://voxmap/experiments/<id>/results/` を notes.md に追記する

9. **実験記録 commit の提示** (commit は提示のみ・自動でやらない):
   - 手順5〜7 で更新した `experiments/<id>/notes.md`・`docs/experiments/<theme>/<id>.md`・
     `docs/experiments/<theme>/_index.md` を**手順2の code commit とは別 commit** にすることを提案する
   - commit message 案を提示してユーザーが OK したら commit:
     ```
     update: <id> 実行結果記録 (DER=X.XXX, RTF=Y.YYY)
     ```
   - この commit hash が「この結果を出した実装」のリファレンスポイントになる。
     `notes.md` の「実行」行に記録された `git_commit` と対応させることで
     `git show <hash>` で実装を即座に参照できる
   - `results/` 配下は gitignore なので add 対象外。docs/ は symlink 先のため
     `git add` 対象として認識される範囲で扱う
   - 失敗実験の場合も同様に「失敗ログ追記」を別 commit で残す

10. **PR 作成の提案** (commit 完了後):
   - `gh pr list --head exp/<id>` で既存 PR がないことを確認
   - GCS ファイル一覧を取得 (`sync-results list` 経由):
     ```
     Skill(skill="sync-results", args="list experiments/<id>")
     ```
   - 以下の body を組み立てて `gh pr create` を提案する (実行はユーザー確認後):
     ```
     gh pr create --title "exp: <id> (DER=X.XXX, RTF=Y.YYY)" --body "$(cat <<'EOF'
     ## 実験: <id>

     **仮説**: <仮説1行>

     ## 変更点 (vs ベースライン)

     - <変更点>

     ## 結果

     | Metric | この実験 | ベースライン | Δ |
     |---|---|---|---|
     | DER (micro) | X.XXXX | X.XXXX | ±0.0000 |
     | DER (macro) | X.XXXX | X.XXXX | ±0.0000 |
     | RTF | X.XXXX | X.XXXX | -X.XXXX (X.XXx↑) |

     実行: `<commit>` @ <date> device=<device> hw=<hw>

     ## 結果データ (GCS)

     `gs://voxmap/experiments/<id>/results/` (sync-results で取得):

     ```
     <sync-results list の実出力>
     ```

     ## リンク

     - ノート: `docs/experiments/<id>.md`
     - Config: `experiments/<id>/config.yaml`

     ## チェックリスト

     - [x] metrics.json 記録済み
     - [ ] docs 考察記入済み
     - [x] GCS アップロード済み
     EOF
     )"
     ```
   - 仮説・変更点は `docs/experiments/<id>.md` の「仮説 / ゴール」「変更点」セクションから転記する
   - 考察が未記入の場合、チェックリストの「docs 考察記入済み」は `[ ]` のまま残す
   - **PR は自動作成しない**。コマンド案を提示してユーザーが OK したら実行する

## 考察・次にやることのゲート

結果テーブルを埋めたあと、**必ずユーザーに以下を伝える**:

> 「結果を記録しました。`docs/experiments/<id>.md` の **考察セクション** に解釈・結論を記入してください。
> 考察が記入されるまで、次の実験計画の提案は行いません。」

次の実験提案 (`次にやること` の記入・`experiment-design` の起動) は、
ユーザーが「考察を書いた」「続けて良い」と明示するまで **行わない**。

## やってはいけないこと

- 「考察」「次にやること」を勝手に断定で埋めない (観察事実のドラフト提案に留める)
- 考察が空のまま次の実験計画を提案・起動しない
- `experiments/*/notes.md` に散文を書かない (結果テーブルと実行情報のみ)
- `metrics.json` を notes に丸ごと貼り付けない (要約だけ)
- 失敗実験を捨てない・隠さない。同じテンプレで記録する
- `results/` 内のファイルをコミット対象にしない (gitignore済)
- **commit を自動実行しない** (手順2と手順9はユーザー確認必須)。
  「コード変更」と「実験記録」は別 commit に分ける

## 参考

- 実験ワークフロー全体: `experiments/README.md` / `docs/experiments/<テーマ日付>_<テーマ名>/_index.md`
- 結果記録の項目仕様: `experiments/README.md` の「記録すべき項目」
