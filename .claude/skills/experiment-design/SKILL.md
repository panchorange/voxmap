---
name: experiment-design
description: 新しい話者分離の実験 (experiments/ 配下のディレクトリ) を作りたいとき起動する。仮説・config・期待する効果・評価メトリクスをテンプレートに沿って整理する。
---

# experiment-design

`experiments/<テーマ日付>_<テーマ名>/<日付>_<名前>/` を新規作成するときの定型作業を行う。

## いつ起動するか

- ユーザーが「新しい実験を始めたい」「〜を試したい」と言ったとき
- ablation study や hyperparameter sweep の準備
- 仮説検証のための pipeline 変更を構成するとき

## 手順

0. **前実験の考察チェック** (ユーザーが「〜から続けて」と言った場合):
   - 前実験の `docs/experiments/<前id>.md` の「考察」セクションが空・プレースホルダーなら
     **「前実験 (<前id>) の考察が未記入です。考察を書いてから次の実験に進むことを推奨します。続けますか?」** と確認する
   - ユーザーが「続ける」と言った場合のみ以降を進める

1. ユーザーに以下を確認する (既に話に出ていれば省略):
   - 実験の名前 (短い英語)
   - 仮説 ("Xを変えるとYが改善するはず")
   - ベースとなる config (通常は `configs/pipeline/baseline.yaml`)
   - 評価データ
   - 実行デバイス (mps / cuda / cpu)。実行環境が確定していれば以下のコマンドでハードウェア詳細を取得する:
     ```bash
     # macOS (Apple Silicon)
     system_profiler SPHardwareDataType | grep -E "Model Name|Chip|Memory:"
     # CUDA (Linux / Windows WSL)
     nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
     uname -srm
     ```
     取得した情報を `hw=` フィールドに記録する (例: `hw=MacBookPro-M4-Max-48GB`, `hw=RTX5070Ti-16GB-Win11`)

2. ブランチを作成する:
   ```bash
   git checkout -b exp/YYYY-MM-DD_<name>
   ```
   ブランチ名は実験ディレクトリ名と完全一致させる (CLAUDE.md の命名規則)。
   既に同名ブランチがあれば `git checkout exp/YYYY-MM-DD_<name>` でスイッチするだけ。

3. **テーマディレクトリを確認し**、`experiments/<theme>/YYYY-MM-DD_<name>/` を作成する。
   テーマは `docs/theme/` の最新ファイル名から判断する (例: `2026-05-07_研究テーマ`, `2026-05-27_ASR+diarization`)。
   不明な場合はユーザーに確認する。

4. ベース config をコピーして変更点だけ編集

4. `experiments/<id>/notes.md` は **結果記録専用**。散文は書かない:
   ```markdown
   # <実験名>

   docs: [[docs/experiments/<実験名>]]

   ## 結果

   | Metric | この実験 | ベースライン (<前id>) | Δ |
   |---|---|---|---|
   | DER (micro) | — | — | — |
   | DER (macro) | — | — | — |
   | RTF | — | — | — |

   実行: — @ — device=— hw=—
   per-file 詳細: `results/metrics.json` 参照
   GCS: gs://voxmap/experiments/<実験名>/results/
   ```
   仮説・変更点・考察はすべて `docs/experiments/` 側に書く。

5. `docs/experiments/<id>.md` (Obsidian) を作成。こちらに仮説・変更点・評価条件・考察・次にやること を書く:
   ```markdown
   # <実験名>

   関連: [[_index]] / [[../theme/...]] / [[<前実験>]]

   リポジトリ側: `experiments/<id>/{config.yaml, run.py, notes.md}`
   結果データ: `experiments/<id>/results/metrics.json` (gitignore)

   ## 仮説 / ゴール
   ## 変更点 (vs ベースライン)
   ## 評価条件

   | 項目 | 値 |
   |---|---|
   | データ | |
   | 音声 | |
   | DER | collar=0.25s, skip_overlap=true |
   | device | mps / cuda / cpu |
   | hardware | (例: MacBook Pro M4 Max 48GB unified / RTX 5070 Ti 16GB VRAM, Win11) |
   | 許容 DER 劣化 | ±0.01 以内 |

   ## 結果
   (実行後に追記)
   ## 考察
   (実行後に追記)
   ## 次にやること
   (考察記入後に追記)
   ```

6. `docs/experiments/<theme>/_index.md` に「⏸実行待ち」行を追加 (テーマ別 `_index.md` が無ければ作成する)

8. 過去の実験 (`docs/experiments/`) で類似のものがあれば参照させる

9. 作成したファイル (`config.yaml`, `run.py`, `notes.md`, `docs/experiments/<id>.md`) を
   初期 commit するよう提案する:
   ```
   add: experiments/<id> 実験設計 (仮説・config・run.py)
   ```
   この commit hash が「実装の出発点」になる。

## 注意

- ディレクトリ名の日付は `date +%Y-%m-%d` で取る
- `experiments/*/notes.md` は機械的に更新される前提のファイル。人間が散文を書く場所ではない
- `results/` 配下は gitignore なので、数値は必ず notes.md / docs/*.md に転記する
