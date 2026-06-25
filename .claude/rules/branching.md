# ブランチ命名

`main` から切り、用途別に以下のプレフィックスを使う。

| prefix | 用途 | 主な変更先 | 例 |
|---|---|---|---|
| `exp/<date>_<name>` | **1実験1ブランチ**。test data で DER/RTF を測る | `experiments/<theme>/<id>/` | `exp/2026-05-10_pyannote4_self-implement` |
| `profile/<name>` | **速度の計測・診断** (micro-benchmark)。特定 op の wall time / FLOPs / params を測る | `profiles/<theme>/<date>_<name>/`, `docs/profiles/<theme>/` | `profile/campplus-vs-resnet34` |
| `analysis/<name>` | **精度の量的分析・可視化**。DER 分解 / 予測因子の相関 / clustering 可視化など (速度ではなく精度・データ特性) | `analysis/<theme>/<date>_<name>/`, `docs/analysis/<theme>/` | `analysis/stride-confusion-cause` |
| `research/<name>` | **量的測定を伴わない探索**。論文読み・PoC・捨てる前提の調査 | `docs/research/` のみ | `research/tts-survey` |
| `feature/<name>` | ライブラリ機能追加・**本番 config 昇格**・ツール開発・skill 追加 | `src/`, `scripts/`, `.claude/skills/`, `configs/` | `feature/compare-runs-skill`, `feature/promote-baseline-campplus` |
| `baseline/<name>` | 外部実装のリファレンス取り込み・再現 | `src/voxmap/models/`, `experiments/` | `baseline/pyannote4` |
| `fix/<name>` | バグ修正 | どこでも | `fix/ahc-empty-cluster` |

## 切り口の整理

**目的と測定の種類**で見ると:

```
exp/      ← pipeline 全体を eval data で測る (DER + RTF)
profile/  ← 速度の micro-benchmark (wall time, FLOPs)
analysis/ ← 精度・データの量的分析 (DER 分解, 相関, 可視化)
research/ ← 量的測定なし (論文・読書ノート・PoC)
```

profile/ (速度) と analysis/ (精度) が対称。research/ は量的測定を伴わない質的探索に限定。

**判断軸は「指標」ではなく「目的 × 対象」** (DER か RTF かで切ると profile と exp が被るため):

| | 目的 | 対象 | 測る指標 | データ量 |
|---|---|---|---|---|
| **experiments/** | 「この構成を採用するか」の意思決定 | **pipeline 全体** | テーマの主要指標**一式** (精度+速度をまとめて) | dev サブセット中心、最終候補のみ full |
| **profiles/** | 速度の原因究明・最適化 | 単一モジュール/op | **速度のみ** (wall time / RTF / throughput / FLOPs)。**精度指標 (DER/CER) は測らない** | 1〜数ファイル |
| **analysis/** | 精度の原因究明・可視化 | 出力の中身 | DER 分解 / 混同 / cluster purity / 相関 | 任意 |

**experiments の主要指標一式** (テーマごと):
- diarization (pyannote 系) → **DER / RTF / 話者消失 / 話者数推定誤り**
- ASR-diarization (AER) → 上記に加え **CER / WER**

**experiments のデータ量**: dev サブセット (例: AMI 2〜4本) で反復イテレーションし、本番昇格候補・最終確認のときだけ full set (AMI 16本) を回す。**dev で回した実験を、良ければ同じ `experiments/<theme>/<id>/` ディレクトリのまま full set まで回してよい** (別 id を切らなくてよい)。`notes.md` に対象 (`dev N本` / `full 16本`) を必ず明記し、compare-runs で混ざらないようにする。

**典型フロー** (ASR-diarization の例): profile で ASR 単体の最速 config を特定 (速度の結論だけ出す) → その config を pipeline に組み込み experiments で DER/CER/WER/RTF を一式測る → 精度の原因を掘るなら analysis。profile で config 選定が完結して experiments に流れない、は非対称なので避ける。

**成果物の文書化先**:

| ブランチ | 主な文書化先 |
|---|---|
| `exp/<id>` | `experiments/<theme>/<id>/notes.md` (結果) + `docs/experiments/<theme>/<id>.md` (考察) |
| `profile/<name>` | `profiles/<theme>/<date>_<name>/notes.md` (キー指標) + `docs/profiles/<theme>/<name>.md` (詳細・考察) |
| `analysis/<name>` | `analysis/<theme>/<date>_<name>/analyze.py` (再現可能な分析) + `docs/analysis/<theme>/<name>.md` (目的・結果・考察) |
| `research/<name>` | `docs/research/<name>.md` (定性まとめ) |
| `feature/promote-*` | `docs/design/decisions/<date>_<name>.md` (**ADR 必須**) |

## ADR (Architecture Decision Record)

判断を残すべきケースは `docs/design/decisions/<date>_<name>.md` に書く。
テンプレ: `docs/design/decisions/_template.md`

**書くタイミング**:
- 本番 config (`configs/pipeline/baseline.yaml`) の変更
- ライブラリ方針の転換 (外部依存 → vendor 化など)
- 「なぜ A ではなく B を選んだか」を半年後の自分に説明したいとき

`feature/promote-*` の PR では ADR をセットで commit する。

## 使い分けで迷ったとき

- **実験中にライブラリ本体も直したくなった**
  - 修正が小さく実験に必須 → `exp/...` ブランチに混ぜてOK (PR説明で言及)
  - 修正が大きい / 他実験でも使う → 一旦 `feature/...` を切って先にmergeしてから `exp/...` をrebaseする
- **実験ブランチの日付**: ブランチ名の日付は `experiments/<id>/` 作成日に固定する (作業が翌日以降にずれてもブランチ名は変えない。ディレクトリと一致させるのが優先)
- **`baseline/` vs `exp/`**: 公開実装をそのまま動かす段階は `baseline/`、自分のconfig/コードで派生させたら `exp/`
- **`profile/` vs `exp/`**: pipeline 全体を test data で回すなら `exp/`、特定モジュールだけ計測するなら `profile/`
- **`profile/` vs `analysis/`**: 測る対象が**速度** (wall time / FLOPs) なら `profile/`、**精度・データ特性** (DER 分解 / 相関 / clustering 可視化) なら `analysis/`。profile-run スキルは速度前提なので精度分析には使わない
- **`analysis/` vs `research/`**: 量的分析スクリプト (`analysis/<date>_<name>/analyze.py`) を伴うなら `analysis/`、読書・PoC など量的測定なしなら `research/`
- **`fix/` vs `feature/`**: 既存の振る舞いを正すなら `fix/`、新しい振る舞いを足すなら `feature/` (リファクタは挙動を変えないので `feature/` 寄り)
- **PR単位**: `exp/<id>` ブランチは notes.md と config.yaml の確定をもって1PR。途中経過はブランチ内コミットでOK
