---
name: setup-theme
description: 新しい実験テーマを立ち上げるとき起動する。experiments/ analysis/ profiles/ それぞれに <テーマ日付>_<テーマ名>/ フォルダと、その場所が何をするか・テーマの主要指標とゴールを明記した README.md を作り、docs/theme/<theme>.md に3者をつなぐ概要を書く。個別の実験/分析/計測の新規作成は experiment-design / analysis-design / profile-design のほう。
---

# setup-theme

新しい実験テーマ (`<テーマ日付>_<テーマ名>`) を立ち上げるときの定型作業。
個別の `<id>/` を作る前に、**テーマの器**を3エリア (experiments / analysis / profiles) に用意し、
「このテーマは何を達成する場で、各フォルダで何を測るのか」を README に明記する。

## いつ起動するか

- 新しい研究テーマを始めるとき (例: `pyannote31-pe`, `ASR-diarization`)
- 既存テーマの README が無く、後から整備したいとき

個別の実験/分析/計測を1件作るのは `experiment-design` / `analysis-design` / `profile-design`。
このスキルは**その上位のテーマ単位**を作る。

## 前提: 判断軸 (CLAUDE.md「切り口の整理」と一致させる)

| エリア | 目的 | 対象 | 測る指標 | データ量 |
|---|---|---|---|---|
| **experiments/** | 「この構成を採用するか」の意思決定 | pipeline 全体 | テーマの主要指標**一式** (精度+速度) | dev サブセット中心、最終候補のみ full |
| **profiles/** | 速度の原因究明・最適化 | 単一モジュール/op | **速度のみ** (wall time / RTF / throughput / FLOPs)。DER/CER は測らない | 1〜数ファイル |
| **analysis/** | 精度の原因究明・可視化 | 出力の中身 | DER 分解 / 混同 / cluster purity / 相関 | 任意 |

## 手順

1. ユーザーに以下を確認する (話に出ていれば省略):
   - **テーマ名** (短い英語 kebab-case。例: `pyannote31-pe`, `ASR-diarization`)
   - **テーマのゴール** (1〜2文。何を達成したら成功か)
   - **experiments の主要指標一式** — このテーマの実験で必ず揃える指標。
     - diarization 系 → DER / RTF / 話者消失 / 話者数推定誤り
     - ASR-diarization (AER) → 上記に加え CER / WER
   - **dev サブセット** と **full set** の定義 (例: dev=AMI 2本 / full=AMI 16本)
   - profiles で最適化したい主対象 (例: embedding 単体, ASR モデル単体) ※未定なら空欄可
   - analysis で掘りたい精度の問い (例: stride による話者混同) ※未定なら空欄可

2. テーマ日付を取る: `date +%Y-%m-%d`。テーマ ID は `<テーマ日付>_<テーマ名>`。

3. 3エリアにテーマフォルダと README を作成する:
   ```
   experiments/<theme>/README.md
   analysis/<theme>/README.md
   profiles/<theme>/README.md
   ```
   README は下記テンプレを使い、**各フォルダが何をする場所か**と**テーマ固有のゴール**を簡潔に書く。

   ### experiments/<theme>/README.md
   ```markdown
   # <テーマ名> — experiments

   pipeline 全体を回し、**この構成を採用するか**を主要指標一式で判断する場。

   ## テーマのゴール
   <例: pyannote → DER / RTF / 話者消失 を改善する>
   <例: ASR-diarization → pyannote テーマと同等の RTF を保ちつつ、可能なら WER を悪化させない>

   ## 主要指標一式 (毎回揃える)
   - <DER / RTF / 話者消失 / 話者数推定誤り / (AER なら CER / WER)>

   ## データ
   - dev サブセット: <例: AMI 2本> — 反復イテレーション用
   - full set: <例: AMI 16本> — 本番昇格候補・最終確認のみ
   - dev で回した実験は、良ければ**同じ `<id>/` のまま** full set まで回してよい (別 id を切らない)。
     notes.md に対象 (`dev N本` / `full 16本`) を必ず明記する。

   ## 個別実験の作り方
   `/experiment-design` → `experiments/<theme>/<日付>_<名前>/`
   ```

   ### profiles/<theme>/README.md
   ```markdown
   # <テーマ名> — profiles

   単一モジュール/op の**速度**を計測し、遅い原因を特定・最適化する場。
   **精度指標 (DER/CER) はここでは測らない** — 速度の結論だけ出して experiments に渡す。

   ## このテーマで最適化したい対象
   - <例: ASR モデル (parakeet) 単体の RTF / batch / fp16>

   ## 測る指標
   - wall time / RTF / throughput / module breakdown / (FLOPs・params)
   - latency は mean/std だけでなく p5/p25/p50/p75/p95 を出す (テール = UX)

   ## 典型フロー
   profile で最速 config を特定 → その config を pipeline に組み込み experiments で精度込み判断。

   ## 個別計測の作り方
   `/profile-design` → `profiles/<theme>/<日付>_<名前>/`
   ```

   ### analysis/<theme>/README.md
   ```markdown
   # <テーマ名> — analysis

   pipeline 出力の中身を分解・可視化し、**なぜその精度なのか**を量的に掘る場 (速度は profiles)。

   ## このテーマで掘りたい問い
   - <例: stride を上げると話者混同がどう増えるか / cluster purity と DER の相関>

   ## 測る/可視化するもの
   - DER 分解 (miss / FA / confusion) / 混同行列 / cluster purity / 話者数推定誤り / 相関・可視化

   ## 個別分析の作り方
   `/analysis-design` → `analysis/<theme>/<日付>_<名前>/`
   ```

4. `docs/theme/<theme>.md` (Obsidian) を作成 or 追記し、3エリアをつなぐ概要を書く。
   既に `docs/theme/<theme>.md` がある場合は、下記「役割分担」節を追記する形にする。
   ```markdown
   # <テーマ名>

   関連: [[../experiments/<theme>/_index]] / [[../profiles/_index]] / [[../analysis/_index]]

   ## ゴール
   <テーマのゴール 1〜2文>

   ## 3エリアの役割分担

   | エリア | このテーマでの役割 | 主要指標 |
   |---|---|---|
   | experiments | <pipeline 全体で採用判断> | <DER/RTF/話者消失 (+CER/WER)> |
   | profiles | <ASR/embedding 単体の速度最適化> | wall time / RTF / breakdown |
   | analysis | <精度劣化の原因分解・可視化> | DER 分解 / purity / 相関 |

   ## 流れ
   profile で速度の勝者 config → experiments で主要指標一式の採用判断 → 悪い箇所を analysis で分解。
   ```

5. docs 側のテーマ別 `_index.md` が無ければ作成する (`docs/experiments/<theme>/`, `docs/analysis/<theme>/`, `docs/profiles/<theme>/` 配下)。
   experiment-design / analysis-design / profile-design が個別ノートを追記する受け皿になる。

6. 作成したファイルを初期 commit するよう提案する (`feature/setup-theme-<name>` ブランチ推奨):
   ```
   add: <テーマ名> テーマ立ち上げ (experiments/profiles/analysis の README + docs/theme)
   ```

## 注意

- README は「**何をする場所か** + **テーマ固有のゴール/主要指標**」を簡潔に。手順の重複は書かず、個別作成は各 design スキルに委ねる。
- 指標セットは CLAUDE.md「切り口の整理」と矛盾させない (experiments=主要指標一式 / profiles=速度のみ)。
- テーマ名・日付の表記はリポジトリ側 (`experiments/<theme>/`) と docs 側 (`docs/.../<theme>/`, `docs/theme/<theme>.md`) で完全一致させる。
- `results/` 配下は gitignore。README は git 管理対象。
