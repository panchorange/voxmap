---
name: profile-run
description: 既存の profiles/<date>_<name>/profile.py を走らせ、結果から wall time / throughput / module breakdown を取り出して notes.md と docs/profiles/<name>.md を更新する。計測を「実行→記録」を一連で済ませたいときに起動。
---

# profile-run

`profiles/<date>_<name>/` の計測を実行し、結果を記録する。

## いつ起動するか

- 既存の profile ディレクトリを「走らせて結果を残す」とき
- 実装変更後に再計測して数字を上書きしたいとき
- 過去の `results/report.md` から記録だけし直したいとき
- 特定モジュールの **std/分布の正体を切り分けたい**とき → `--focused` モードで再計測

新規計測を**作成**したいだけなら `profile-design` のほう。

## 手順

1. **引数確認**（足りなければユーザーに聞く）:
   - profile ID（`profiles/<date>_<name>/` の `<date>_<name>`）
   - 実行モード:
     - 通常: full sweep + breakdown（既定）
     - `--detailed`: op-level breakdown も追加
     - `--focused`: aggregate スキップ・固定条件で高 n_reps、生データ + plots 出力
   - 既に `results/report.md` があれば「再実行 / 既存を使う」を確認

2. **実行前 commit の確認**:
   - `git status` を確認し、`src/voxmap/` 等に変更があれば commit を提案
   - 理由: notes.md に記録する git_commit をクリーンなハッシュにするため

3. **実行**:
   - 通常モード:
     ```bash
     uv run python profiles/<date>_<name>/profile.py \
       --out profiles/<date>_<name>/results/report.md [--detailed]
     ```
   - focused モード（個別モジュールの std/分布調査用）:
     ```bash
     uv run python profiles/<date>_<name>/profile.py \
       --out profiles/<date>_<name>/results/report.md \
       --focused \
       --dtype fp16 --batch-size 64 --n-reps 100 \
       --focus-module xvector.block3
     ```
     生成物（`results/` 配下、gitignore）:
     - `report.md` — breakdown テーブル（mean / std / p5 / p25 / p50 / p75 / p95 / share）+ plots パス
     - `breakdown_raw_times.json` — per-rep 生データ（後で再プロットや統計検定に使える）
     - `breakdown_boxplot.png` — 全モジュールの per-rep 分布（箱ひげ）
     - `<focus_module>_histogram.png` — `--focus-module` の per-rep 分布（KDE 付き）

     **percentile を必ず出す**: テールレイテンシは UX への影響が大きいので、mean/std だけでなく p5/p25/p50/p75/p95 (中央値 + 上下テール) を併記する。p95-p5 が mean に対して大きいモジュールはばらつき源として要警戒。

4. **結果の抽出**（`results/report.md` から読む）:
   - 通常モード: aggregate sweep / module breakdown テーブル（share 順）
   - focused モード: breakdown テーブル（percentile 列 p5/p25/p50/p75/p95 付き）+ plot ファイル名
   - ハードウェア情報:
     ```bash
     system_profiler SPHardwareDataType | grep -E "Model Name|Chip|Memory:"
     ```

5. **`profiles/<date>_<name>/notes.md` を更新**:
   - 「計測条件」の `—` を実数で置換
   - 「キー指標」テーブルを埋める（end-to-end / 上位 3〜4 モジュール）
   - focused モードの場合は **percentile 列 (p5/p25/p50/p75/p95) も含めて**転記
   - `実行: <git_commit_short> @ <completed_at> device=<device> hw=<hw>` を記入
   - 散文は書かない。考察は `docs/profiles/` 側のみ

6. **`docs/profiles/<name>.md` を更新**:
   - aggregate sweep / module breakdown テーブルを貼る
   - focused モードの場合は plot のファイルパスを **参照リスト**で記載する (repo path: `profiles/<id>/results/breakdown_boxplot.png` 等)。docs/ は Obsidian symlink で repo 外にあるため画像埋め込み (`![](...)`) は使わない
   - 「考察」セクションには**観察事実のみ** bullet で 1〜3 個提案する（解釈はユーザーが書く）

7. **GCS に results をアップロード** (`sync-results` skill 経由):
   ```
   Skill(skill="sync-results", args="upload profiles/<date>_<name>")
   ```
   - 認証チェックと `gcloud storage rsync` は `sync-results` 側に任せる
   - 失敗した場合はスキップして注意だけ出す（upload 失敗でノート記録まで止めない）
   - upload 後は GCS の URL `gs://voxmap/profiles/<date>_<name>/results/` を notes.md に追記する

8. **記録 commit を提案**（提示のみ・自動実行しない）:
   - 更新した `profiles/<date>_<name>/notes.md` と `docs/profiles/<name>.md` を対象にする
   - commit message 案を提示してユーザーが OK したら commit:
     ```
     update: profiles/<date>_<name> 計測結果記録
     ```
   - `results/` 配下は gitignore なので add 対象外

9. **PR 作成の提案**（commit 完了後）:
   - `gh pr list --head profile/<name>` で既存 PR がないことを確認
   - 以下の body を組み立てて `gh pr create` を提案する（実行はユーザー確認後）:
     ```
     gh pr create --title "profile: <date>_<name>" --body "$(cat <<'EOF'
     ## 計測: <date>_<name>

     **目的**: <何を計測したか1行>

     ## キー指標 (fp16, bs=64 など本番条件)

     | module | mean (ms) | share |
     |---|---|---|
     | ... | ... | ... |
     | (end-to-end) | ... | 100% |

     実行: `<commit>` @ <date> device=<device> hw=<hw>

     ## 結果データ (GCS)

     `gs://voxmap/profiles/<date>_<name>/results/` (sync-results で取得):

     ```
     <sync-results list の実出力>
     ```

     ## リンク

     - ノート: `profiles/<date>_<name>/notes.md`
     - 詳細レポート: `docs/profiles/<name>.md`

     ## チェックリスト

     - [x] results/report.md 記録済み
     - [ ] docs 考察記入済み
     - [x] GCS アップロード済み
     EOF
     )"
     ```
   - **PR は自動作成しない**。コマンド案を提示してユーザーが OK したら実行する

## 考察のゲート

結果記録後、必ずユーザーに伝える:

> 「結果を記録しました。`docs/profiles/<name>.md` の **考察セクション** に解釈・結論を記入してください。」

次の打ち手の提案は、ユーザーが「考察を書いた」と明示するまで行わない。

## やってはいけないこと

- 「考察」を勝手に断定で埋めない（観察事実のドラフト提案に留める）
- `results/` 内ファイルをコミット対象にしない（gitignore 済）
- `notes.md` に散文を書かない（指標と実行情報のみ）
- commit を自動実行しない（ユーザー確認必須）
