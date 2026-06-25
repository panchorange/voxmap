# voxmap

話者分離 (speaker diarization) のライブラリ兼、精度向上のための実験リポジトリ。

VAD・話者埋め込み・クラスタリングを差し替え可能なコンポーネントとして提供し、
config駆動で実験を回せる構成になっている。

## 全体像

```
voxmap/
├── src/voxmap/         # ライブラリ本体 (importして使う)
│   ├── io/              # 音声・事前セグメント (Whisper等) の入力
│   ├── vad/             # 音声区間検出
│   ├── embedding/       # 話者埋め込み
│   ├── clustering/      # クラスタリング
│   ├── pipeline/        # VAD → Embedding → Clustering を合成
│   ├── eval/            # DER / 話者消失 / レイテンシ / 可視化
│   ├── registry.py      # コンポーネント登録
│   └── types.py         # Segment, Diarization など共通型
├── configs/            # 本番パイプラインのYAML (実験パラメータは experiments/ 側)
├── experiments/<theme>/  # テーマ別 → 実験ごとのconfig + notes (results/ はgitignore)
├── profiles/<theme>/   # テーマ別 → モジュール単位の速度計測スクリプト + notes (results/ はgitignore)
├── analysis/<theme>/   # テーマ別 → 精度・データ特性の量的分析/可視化スクリプト + notes (results/ はgitignore)
├── research/           # 量的測定なしの探索コード・PoC・可視化スクリプト
├── scripts/            # CLI: diarize / evaluate / compare_runs / analyze_pipeline / sync_results / sync_check
├── tests/
├── data/               # gitignore対象 (raw/processed)
└── docs/               # → Obsidian保管庫へのsymlink (設計書・実験ノート・研究メモ)
```

## セットアップ

```bash
make setup
```

`uv` で依存をインストールし、pre-commit (ruff + mypy) を有効化する。

PR 作成の自動化 (skill / `gh pr create`) には別途 GitHub CLI が必要:

```bash
brew install gh
gh auth login
```

## 使い方

### 1. ライブラリとして

```python
from voxmap.pipeline import build_pipeline

pipeline = build_pipeline("configs/pipeline/baseline.yaml")
diarization = pipeline.run("path/to/audio.wav")
```

### 2. CLIとして

```bash
# 話者分離を実行 (RTTM出力)
uv run python scripts/diarize.py audio.wav --config configs/pipeline/baseline.yaml -o out.rttm

# 評価 (DER + 話者消失 + 可視化)
uv run python scripts/evaluate.py --pred out.rttm --ref reference.rttm --out results/

# 複数の実験結果を比較
uv run python scripts/compare_runs.py experiments/<theme>/2026-05-01_baseline experiments/<theme>/2026-05-02_xxx

# pipeline の中間出力を可視化して精度を分析 (segmentation / embedding / clustering)
uv run python scripts/analyze_pipeline.py \
    --config experiments/<theme>/<id>/config.yaml --meetings IS1009a,EN2002c \
    --out analysis/<theme>/<id>/results
```

### 3. 実験を追加する

`experiments/<テーマ>/<日付>_<名前>/` にディレクトリを作って `config.yaml` と `run.py` を置く。
テーマは `docs/theme/` の最新ファイル名と対応する (例: `2026-05-07_pyannote31-pe`)。
詳細は [experiments/README.md](experiments/README.md) を参照。

**git ブランチ管理:**

各実験は `exp/<日付>_<名前>` という専用ブランチで管理する。ブランチ名は実験ディレクトリ名と完全一致させる。
それ以外の作業 (プロファイリング・調査・本番昇格・機能追加) は別プレフィックスを使う。詳細は下記「ブランチ戦略」セクション。

```bash
# 実験作成時 (experiment-design skill で自動)
git checkout -b exp/2026-05-12_pyannote4_emb_fp16

# 実装の commit (run.py / config.yaml の変更)
git commit -m "update: experiments/2026-05-12_pyannote4_emb_fp16 実装 (..."

# 実験実行
uv run python experiments/2026-05-12_pyannote4_emb_fp16/run.py

# 結果を記録して commit (experiment-run skill で自動)
git commit -m "update: 2026-05-12_pyannote4_emb_fp16 実行結果記録 (DER=0.0810, RTF=0.107)"
```

`metrics.json` に記録される `git_commit` hash により、「この結果がどのコミットのコードで出たか」が追跡可能になる。
後から `git show <hash>` で実装を参照できる。

## ブランチ戦略

`main` から切る。用途別に以下のプレフィックスを使う:

| prefix | 用途 | 主な変更先 | 例 |
|---|---|---|---|
| `exp/<date>_<name>` | 1実験1ブランチ。test data で DER/RTF を測る | `experiments/<theme>/<id>/` | `exp/2026-05-14_campplus` |
| `profile/<name>` | 速度のモジュール計測・診断 (micro-benchmark) | `profiles/<theme>/<date>_<name>/`, `docs/profiles/<theme>/` | `profile/campplus-vs-resnet34` |
| `analysis/<name>` | 精度・データ特性の量的分析・可視化 (DER 分解 / 相関 / clustering 可視化) | `analysis/<theme>/<date>_<name>/`, `docs/analysis/<theme>/` | `analysis/stride-confusion-cause` |
| `research/<name>` | 量的測定なし。論文読み・PoC・捨てる前提の調査 | `docs/research/` のみ | `research/tts-survey` |
| `feature/<name>` | ライブラリ機能追加・本番 config 昇格・ツール開発・skill 追加 | `src/`, `scripts/`, `.claude/skills/`, `configs/` | `feature/compare-runs-skill` |
| `baseline/<name>` | 外部実装のリファレンス取り込み | `src/voxmap/models/`, `experiments/` | `baseline/pyannote4` |
| `fix/<name>` | バグ修正 | どこでも | `fix/ahc-empty-cluster` |

### 切り口

**目的と測定の種類**:

- `exp/` — pipeline 全体を eval data で測る (DER + RTF)
- `profile/` — **速度**の micro-benchmark (wall time, FLOPs)
- `analysis/` — **精度・データ特性**の量的分析・可視化 (DER 分解 / 相関 / clustering 可視化)。profile/ の精度版
- `research/` — 量的測定なし (論文・PoC)

**成果物の文書化先**:

| ブランチ | 文書化先 |
|---|---|
| `exp/<id>` | `experiments/<theme>/<id>/notes.md` + `docs/experiments/<theme>/<id>.md` |
| `profile/<name>` | `profiles/<theme>/<date>_<name>/notes.md` + `docs/profiles/<theme>/<name>.md` |
| `analysis/<name>` | `analysis/<theme>/<date>_<name>/analyze.py` + `docs/analysis/<theme>/<name>.md` |
| `research/<name>` | `docs/research/<name>.md` |
| `feature/promote-*` | `docs/design/decisions/<date>_<name>.md` (**ADR 必須**) |

### ADR (判断記録)

本番 config やライブラリ方針を変えるときは `docs/design/decisions/<date>_<name>.md` を書く。
テンプレ: `docs/design/decisions/_template.md`。

書くべきタイミング:
- `configs/pipeline/baseline.yaml` を変更するとき
- ライブラリの方針転換 (外部依存 → vendor 化など)
- 後から「なぜ A ではなく B を選んだか」が必要になりそうなとき

`feature/promote-*` の PR は ADR をセットで commit する。

詳細な使い分け (`baseline/` vs `exp/`、`profile/` vs `research/` 等) は [CLAUDE.md](CLAUDE.md#ブランチ命名) を参照。

## コンポーネントのカスタマイズ

各 `*/base.py` に Protocol が定義されているので、それを満たすクラスを書いて
`registry.py` に登録すれば configs の `name:` で指定できる。

```yaml
# experiments/<theme>/<id>/config.yaml の pipeline 部、または configs/pipeline/baseline.yaml
vad:        { name: silero,    threshold: 0.5 }
embedding:  { name: wespeaker, model: voxceleb_resnet34 }
clustering: { name: spectral,  n_clusters: null }
```

## 評価機能

- **DER / JER**: `pyannote.metrics` のラッパ ([eval/der.py](src/voxmap/eval/der.py))
- **話者消失率 / Speaker recall**: 正解話者ごとの被覆率と消失判定 ([eval/speaker_recall.py](src/voxmap/eval/speaker_recall.py))
- **混同行列**: ハンガリアン法による最適マッピング ([eval/confusion.py](src/voxmap/eval/confusion.py))
- **レイテンシ**: RTF + ステージ別内訳 + ピークGPUメモリ ([eval/latency.py](src/voxmap/eval/latency.py))
- **可視化 / pipeline 診断**: segmentation timeline・cos類似行列・dendrogram・PCA を本番 AHC で描く再利用部品 ([eval/visualize.py](src/voxmap/eval/visualize.py))。config から実験と同一の pipeline を組む `build_pipeline_from_config` ([eval/build.py](src/voxmap/eval/build.py)) と合わせ、薄い CLI [scripts/analyze_pipeline.py](scripts/analyze_pipeline.py) や `analysis/<id>/analyze.py` から呼ぶ
- **レポート**: dictで返すので wandb / MLflow / 手書きJSON どれにも繋げられる ([eval/report.py](src/voxmap/eval/report.py))

## 入力形式

通常は音声ファイル単体だが、Whisper等で既にセグメント分割済みの場合は
`vad/from_segments.py` が事前セグメントをVAD出力として扱うので、Pipelineは
何も変更せずに使える。

## docs / Obsidian連携

`docs/` はObsidian保管庫への symlink:

```
docs -> /Users/.../マイドライブ/開発/音声認識/diarization
```

設計書や実験ノートは Obsidian側で書くと、リンクグラフやバックリンクが効く。
Claude Code skillsが `docs/` を自動参照するよう [.claude/skills/](.claude/skills/) に
設定してある。

## Claude Code Skills

`.claude/skills/` に登録された定型作業。Claude Code 上で `/skill名` と入力するか、自然言語で話しかけると起動する。

| skill | 起動タイミング | 主な処理 |
|---|---|---|
| `experiment-design` | 「新しい実験を作りたい」 | `experiments/<theme>/<id>/` 作成・config コピー・docs/notes テンプレ生成・初期 commit 提案 |
| `experiment-run` | 「実験を走らせて結果を整理して」 | `run.py` 実行 → metrics.json 抽出 → notes/docs/_index 更新 → `sync-results` で GCS アップロード → PR 作成提案 |
| `compare-runs` | 「複数実験の DER/RTF を比較したい」 | aggregate + per-meeting の DER/RTF/話者消失率/話者数推定誤り 表を生成 → `docs/experiments/comparisons/<name>/` に markdown 保存 (`--plot` で box/bar chart も) |
| `profile-design` | 「特定モジュールを計測したい」 | `profiles/<日付>_<名前>/` 作成・profile.py / notes.md テンプレ生成 |
| `profile-run` | 「計測を走らせて結果を整理して」 | `profile.py` 実行 → report 抽出 → notes/docs 更新 → `sync-results` で GCS アップロード → PR 作成提案 |
| `analysis-design` | 「精度・データ特性を分析/可視化したい」 | `analysis/<日付>_<名前>/` 作成・analyze.py / notes.md テンプレ生成 (`voxmap.eval.visualize` を import する設計) |
| `analysis-run` | 「分析を走らせて結果を整理して」 | `analyze.py` (or `scripts/analyze_pipeline.py`) 実行 → cluster purity / 話者数誤り / 図の所見抽出 → notes/docs/_index 更新 → `sync-results` → commit 提案 |
| `feature-design` | 「`feature/` ブランチを切る前に設計を固めたい」 | 要件・インタフェース・テスト計画を一枚に整理 |
| `sync-check` | 「実験/計測の同期ズレを確認したい」 | repo / Obsidian docs / `_index.md` / GCS (`gs://voxmap/`) の整合性を一括検査 (`make sync-check` 経由でも可) |
| `sync-results` | 「単一 ID を GCS と同期したい」 | `gcloud storage rsync` ラッパー (upload / download / list / upload-all / download-all)。`experiment-run` / `profile-run` / `analysis-run` から呼ばれる |
| `design-lookup` | 設計・アーキテクチャの質問 | `docs/design/` を参照してから回答 |

### 実験1サイクルの流れ

```
/experiment-design   # ブランチ作成・config・テンプレ生成
  ↓ 実装 (run.py / config.yaml を編集)
/experiment-run      # 実行 → 記録 → GCS (sync-results) → PR
  ↓ docs の考察セクションを記入
次の実験へ
```

profile (速度計測) / analysis (精度分析・可視化) も同じ流れで `/profile-design` → `/profile-run` /
`/analysis-design` → `/analysis-run` で進める。
散らかってきたら `/sync-check` (or `make sync-check`) で repo / Obsidian / GCS の整合性を確認する。

## 開発コマンド

```bash
make lint        # ruff check
make format      # ruff format
make typecheck   # mypy
make check       # lint + typecheck
make test        # pytest
make sync-check  # repo / Obsidian / GCS の整合性検査
```

技術スタック: Python 3.12 / [uv](https://github.com/astral-sh/uv) / [ruff](https://github.com/astral-sh/ruff) / [mypy](https://mypy-lang.org/) (strict) / [pre-commit](https://pre-commit.com/)
