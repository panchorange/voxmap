# リポジトリ構成とドキュメントの場所

## レイアウト要点

- `src/voxmap/` — ライブラリ本体 (src layout)。各コンポーネント (`vad/` `embedding/` `clustering/`) は `base.py` で Protocol を定義し `registry.py` で名前解決する設計
- `configs/` — **本番**パイプラインのYAML (`configs/pipeline/baseline.yaml` がリファレンス)。実験のパラメータは `experiments/<id>/config.yaml` 側で管理し、良い結果が出たら本番にプロモートする運用
- `experiments/<テーマ日付>_<テーマ名>/<日付>_<名前>/` — テーマ別サブディレクトリの下に1実験1ディレクトリ。config + notes はgit管理、`results/` はgitignore
- `profiles/<テーマ日付>_<テーマ名>/<日付>_<名前>/` — テーマ別サブディレクトリの下に1計測1ディレクトリ。profile.py + notes はgit管理、`results/` はgitignore
- `analysis/<テーマ日付>_<テーマ名>/<日付>_<名前>/` — テーマ別サブディレクトリの下に1分析1ディレクトリ。analyze.py はgit管理、`results/` はgitignore。profile/ (速度) と対称
- `scripts/` — CLI (diarize / evaluate / compare_runs)
- `docs/` — **Obsidian保管庫へのsymlink** (Google Drive内)。`[[link]]` 記法あり
- `data/`, `experiments/*/*/results/`, `profiles/*/*/results/`, `analysis/*/*/results/` はgitignore

## ドキュメントの場所

| 内容 | 場所 |
|---|---|
| 設計書・アーキテクチャ判断 | `docs/design/` (Obsidian) |
| 実験の詳細ノート・考察 | `docs/experiments/` (Obsidian) |
| 論文ノート・外部参照・質的探索 | `docs/research/`, `docs/references/` (Obsidian) |
| スプリントタスク管理 | `docs/sprint/` (Obsidian) |
| 実験のconfig/結果 | `experiments/<theme>/<id>/` (リポジトリ) |
| 速度計測スクリプト・キー指標 | `profiles/<theme>/<id>/` (リポジトリ) |
| 速度計測の詳細レポート・考察 | `docs/profiles/<theme>/` (Obsidian) |
| 精度分析スクリプト | `analysis/<theme>/<id>/` (リポジトリ) |
| 精度分析の詳細レポート・考察 | `docs/analysis/<theme>/` (Obsidian) |
| ライブラリAPIの使い方 | `README.md` |

id 形式: `<日付>_<名前>`

設計やアーキテクチャに関する質問が来たら、コードより先に `docs/design/` を読む。
無ければコードを読んで答える。
