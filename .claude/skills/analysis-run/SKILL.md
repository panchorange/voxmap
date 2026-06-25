---
name: analysis-run
description: 既存の analysis/<テーマ日付>_<テーマ名>/<date>_<name>/analyze.py を走らせ、results/report.md から cluster purity / 話者数推定誤り / 図の所見を取り出して notes.md・docs/analysis/<name>.md・docs/analysis/_index.md に転記する。分析を「実行→記録」を一連で済ませたいときに起動。
---

# analysis-run

`analysis/<テーマ日付>_<テーマ名>/<date>_<name>/` の分析を実行し、結果を記録する。
profile-run の精度版。

## いつ起動するか

- 既存の analysis ディレクトリを「走らせて結果を残す」とき
- pipeline/config 変更後に再実行して図・指標を更新したいとき
- 過去の `results/report.md` から記録だけし直したいとき

新規分析を**作成**したいだけなら `analysis-design` のほう。

## 手順

1. **引数確認** (足りなければユーザーに聞く):
   - analysis ID (`analysis/<date>_<name>/` の `<date>_<name>`)
   - 対象 config / 比較対象 (例: baseline vs stride3)
   - 既に `results/report.md` があれば「再実行 / 既存を使う」を確認

2. **実行前 commit の確認**:
   - `git status` を確認し、`src/voxmap/` 等に変更があれば commit を提案
   - 理由: 記録する git_commit をクリーンなハッシュにするため

3. **実行**:
   - 分析固有スクリプト経由:
     ```bash
     uv run python analysis/<date>_<name>/analyze.py --out analysis/<date>_<name>/results
     ```
   - もしくは標準セットの薄い CLI 経由 (config 単体):
     ```bash
     uv run python scripts/analyze_pipeline.py \
       --config experiments/<id>/config.yaml \
       --meetings <m1>,<m2> --dataset ami \
       --out analysis/<date>_<name>/results/<label>
     ```
   - 生成物 (`results/` 配下、gitignore):
     - `report.md` — cluster_purity / 話者数推定誤り (count_error) / n_segments の表
     - `<meeting>_timeline.png` — reference vs predicted timeline + instantaneous count
     - `<meeting>_cluster.png` — cos 類似行列 / dendrogram@threshold / PCA (予測 vs 正解)
     - intermediate キャッシュ (`cache/*.pkl`)

4. **結果の抽出** (`results/report.md` から読む):
   - cluster_purity (1.0 = クラスタが純粋) / count_error (予測話者数 − 正解、+ は過分割 / − は過併合)
   - 図から読める所見 (cluster 境界が滲んでいる / PCA で正解話者が混在 など) を 1〜3 個メモ
   - ハードウェア情報:
     ```bash
     system_profiler SPHardwareDataType | grep -E "Model Name|Chip|Memory:"
     ```

5. **`analysis/<date>_<name>/notes.md` を更新**:
   - 「条件」の `—` を実数で置換
   - 「キー所見」に cluster_purity / count_error の表 + 図から読めた事実を箇条書き
   - `実行: <git_commit_short> @ <completed_at> device=<device>` を記入
   - 散文・解釈は書かない (考察は docs/analysis/ 側のみ)

6. **`docs/analysis/<name>.md` を更新**:
   - report.md の表を貼る
   - 図は **参照リスト**で記載 (repo path: `analysis/<id>/results/<meeting>_cluster.png` 等)。docs/ は Obsidian symlink で repo 外にあるため画像埋め込み (`![](...)`) は使わない
   - 「考察」セクションには**観察事実のみ** bullet で 1〜3 個提案する (解釈はユーザーが書く)

7. **`docs/analysis/_index.md` の一覧表に行を追加** (date / 問い / キー結果 / `[[<name>]]`)。

8. **GCS に results をアップロード** (`sync-results` skill 経由):
   ```
   Skill(skill="sync-results", args="upload analysis/<date>_<name>")
   ```
   - 失敗してもノート記録は止めない。upload 後は `gs://voxmap/analysis/<date>_<name>/results/` を notes.md に追記

9. **記録 commit を提案** (提示のみ・自動実行しない):
   - 更新した `analysis/<date>_<name>/notes.md` と `docs/analysis/<name>.md`・`_index.md` を対象
   - commit message 案:
     ```
     update: analysis/<date>_<name> 分析結果記録
     ```
   - `results/` 配下は gitignore なので add 対象外

## 考察のゲート

結果記録後、必ずユーザーに伝える:

> 「結果を記録しました。`docs/analysis/<name>.md` の **考察セクション** に解釈・結論を記入してください。」

次の打ち手の提案は、ユーザーが「考察を書いた」と明示するまで行わない。

## やってはいけないこと

- 「考察」を勝手に断定で埋めない (観察事実のドラフト提案に留める)
- `results/` 内ファイルをコミット対象にしない (gitignore 済)
- `notes.md` に散文を書かない (指標と所見・実行情報のみ)
- commit を自動実行しない (ユーザー確認必須)
