---
name: profile-design
description: 新しいモジュール単位の計測（micro-benchmark）を始めたいとき起動する。何を計測するか・条件・スクリプト構成をテンプレートに沿って整理し profiles/<theme>/<date>_<name>/ を作成する。
---

# profile-design

`profiles/<テーマ日付>_<テーマ名>/<日付>_<名前>/` を新規作成するときの定型作業を行う。

## いつ起動するか

- 特定モジュールの wall time / throughput / FLOPs を計測したいとき
- 実装変更前後の速度比較をしたいとき（A vs B の micro-benchmark）
- `profile/<name>` ブランチを切る前の設計整理

pipeline 全体を eval data で測るなら `experiment-design` のほう。

## 手順

1. ユーザーに以下を確認する（既に話に出ていれば省略）:
   - 計測の名前（短い英語）
   - **何を計測するか**（モジュール名・関数・モデル名）
   - 計測の目的（ボトルネック特定 / A vs B 比較 / 最適化効果確認）
   - 条件（device / dtype / batch_size sweep / chunk duration）
   - 実行環境:
     ```bash
     system_profiler SPHardwareDataType | grep -E "Model Name|Chip|Memory:"
     ```

2. ブランチを作成する:
   ```bash
   git checkout -b profile/<name>
   ```

3. **テーマディレクトリを確認し**、`profiles/<theme>/<date>_<name>/` を作成する。
   既存テーマを確認する (`ls profiles/`)。該当するテーマがあればその下に作成し、
   無ければ新規テーマディレクトリ `<テーマ日付>_<テーマ名>/` (例: `2026-05-27_ASR-diarization`) を作ってその下に作成する。
   テーマは `docs/theme/` の最新ファイル名からも判断できる。不明な場合はユーザーに確認する。
   ```
   profiles/<theme>/<date>_<name>/
     profile.py   ← 計測スクリプト
     notes.md     ← 条件・キー指標（git 管理）
     results/     ← 生レポート（gitignore）
   ```

4. `profiles/<theme>/<date>_<name>/profile.py` のテンプレートを作成:
   - `REPO_ROOT = Path(__file__).resolve().parents[3]` で repo root を参照
   - 計測の 3 段階を実装: aggregate sweep / module breakdown / （任意）op-level
   - `--out` オプションで `results/report.md` に書き出せるようにする

5. `profiles/<theme>/<date>_<name>/notes.md` を作成:
   ```markdown
   # <date>_<name>

   docs: [[docs/profiles/<theme>/<name>]]

   ## 計測条件

   | 項目 | 値 |
   |---|---|
   | 対象 | |
   | device | |
   | hw | |
   | dtype | |
   | batch_size | |
   | chunk | |
   | n_reps | |
   | warmup | |

   実行: — @ — device=— hw=—
   結果レポート: `results/report.md` 参照（gitignore）

   ## キー指標

   （実行後に追記）
   ```

6. `docs/profiles/<theme>/<name>.md` (Obsidian) を作成:
   ```markdown
   # <name> profiling

   リポジトリ側: `profiles/<theme>/<date>_<name>/{profile.py, notes.md}`
   結果データ: `profiles/<theme>/<date>_<name>/results/report.md` (gitignore)

   ## 計測条件
   ## モジュール構造の読み方
   ## (1) aggregate sweep
   ## (2) module breakdown
   ## 考察
   <!-- ここに手動で考察を追記 -->
   ```

7. 初期 commit を提案する:
   ```
   add: profiles/<theme>/<date>_<name> 計測設計 (profile.py / notes.md)
   ```

## 注意

- `profiles/*/notes.md` はキー指標の記録専用。考察の散文は `docs/profiles/` 側に書く
- `results/` は gitignore。数値は必ず notes.md に転記する
- ブランチ名の日付はディレクトリ作成日に固定する（実験と同じルール）
