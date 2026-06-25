---
name: analysis-design
description: 新しい精度・データ特性の分析 (analysis/ 配下) を始めたいとき起動する。何を可視化/定量するか・対象 pipeline (config)・問いをテンプレートに沿って整理し analysis/<テーマ日付>_<テーマ名>/<date>_<name>/ を作成する。速度計測なら profile-design のほう。
---

# analysis-design

`analysis/<テーマ日付>_<テーマ名>/<日付>_<名前>/` を新規作成するときの定型作業を行う。
profile/ (速度) と対称の **精度・データ特性** カテゴリ。

## いつ起動するか

- ある pipeline / config の中間出力 (segmentation / embedding / clustering) を**可視化して目で見たい**とき
- DER/話者数推定の悪化原因を**定量+可視化で切り分けたい**とき (例: stride で DER 悪化 → clustering が崩れているか)
- 正解 RTTM だけで測れるデータ特性 (turn 密度・自己相関など) を分析したいとき

速度 (wall time / FLOPs) を測るなら `profile-design`、pipeline 全体を eval data で DER 測定するなら `experiment-design` のほう。

## 手順

1. ユーザーに以下を確認する (既に話に出ていれば省略):
   - 分析の名前 (短い英語)
   - **問い / 仮説** (何を確かめたいか。1行)
   - **対象** — 既存 config (`experiments/<id>/config.yaml` or `configs/pipeline/*.yaml`) か、正解 RTTM だけか
   - 出力 — 可視化 (どの中間出力)、定量指標 (cluster purity / 話者数誤り / 自己相関 など)
   - データセット / split (ami / voxconverse, test など)

   **まず既存の metrics.json / RTTM で測れないか**を考える (新規 pipeline 実行は最後の手段)。

2. ブランチを作成する (analysis カテゴリの基盤変更が無ければ `analysis/`、基盤も触るなら `feature/`):
   ```bash
   git checkout -b analysis/<date>_<name>
   ```

3. `analysis/<date>_<name>/` を作成:
   ```
   analysis/<date>_<name>/
     analyze.py   ← 分析スクリプト
     notes.md     ← 問い・条件・キー所見 (git 管理)
     results/     ← 図 + report.md (gitignore: analysis/*/results/)
   ```

4. `analysis/<date>_<name>/analyze.py` のテンプレートを作成:
   - `REPO_ROOT = Path(__file__).resolve().parents[2]` + `sys.path.insert(0, str(REPO_ROOT / "src"))`
   - **可視化の再利用部品は `voxmap.eval.visualize` を import** する (車輪の再発明をしない):
     - `run_with_hooks` / `diagnose_meeting` — pipeline の中間出力を捕捉し timeline + cluster 図 + metrics
     - `plot_segmentation_timeline` / `plot_cluster_diagnostics` / `cluster_metrics` — 個別の図/指標
     - clustering は **本番 AHC (`pipeline.clustering`)** を使う。スクリプト内で再実装しない
   - pipeline は **config から組む**: `voxmap.eval.build.build_pipeline_from_config(config)` (fp16/melspec/per-chunk を実験と一致させる)
   - 標準セット (timeline + cluster 図 + report) で足りるなら、薄い CLI `scripts/analyze_pipeline.py` を呼ぶだけでもよい
   - `--out` で `results/` 配下に図と `report.md` を書き出す

5. `analysis/<date>_<name>/notes.md` を作成:
   ```markdown
   # <date>_<name>

   docs: [[docs/analysis/<name>]]

   ## 問い / 仮説

   <1〜2 行>

   ## 条件

   | 項目 | 値 |
   |---|---|
   | 対象 config | |
   | データセット / split | |
   | 出力 | |

   ## キー所見

   (analysis-run 実行後に埋める。散文は docs/analysis/ 側へ)
   ```

6. `docs/analysis/<name>.md` (Obsidian) の考察ノートを枠だけ作る + `docs/analysis/_index.md` に行を追加。

7. **実行は `analysis-run`** で行う旨を伝える。

## やってはいけないこと

- 可視化/クラスタリングを analyze.py 内で**手実装しない** (lib `voxmap.eval.*` を使う)
- `results/` をコミット対象にしない (gitignore 済)
- notes.md に長い考察を書かない (指標と所見の箇条書きのみ、考察は docs/analysis/)
