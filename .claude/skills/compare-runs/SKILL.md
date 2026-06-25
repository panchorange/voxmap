---
name: compare-runs
description: 複数の experiments/<id>/ の metrics.json を比較し、aggregate / per-meeting の DER・RTF・話者消失率・話者数推定誤り を markdown で出力する。scripts/compare_runs.py を呼び出して結果を整理する。実験を並べて「どれが良いか」を見たいときに起動。
---

# compare-runs

`scripts/compare_runs.py` を呼び出して複数 experiments の比較レポートを
`docs/experiments/comparisons/<name>/comparison.md` に出力し、観察事実だけを
ユーザーに伝える skill。

数値生成は CLI 側、**解釈・結論はユーザー判断**。skill が「勝ち負け」を決めない。

## いつ起動するか

- 「実験 A と B を比べたい」「最近の3実験の DER を並べて」など、複数 experiments を一覧で見たいとき
- ablation study / hyperparameter sweep の結果整理
- 本番昇格 (`feature/promote-*`) 候補を決めるための定量データを揃えるとき

単一実験の実行・記録は `experiment-run` のほう。

## 手順

1. **引数確認** (足りなければユーザーに聞く):
   - 比較対象の実験 ID (2件以上、`experiments/<id>/` の `<id>`)
   - 出力名 (省略可、未指定なら `<id1>_vs_<id2>` で自動)
   - プロット要否 (ユーザーが「グラフも」「chart も」と言ったら `--plot` を付ける)

2. **`metrics.json` の存在確認**:
   - 各 `experiments/<id>/results/metrics.json` が存在するかチェック
   - 無ければ「`<id>` の results/metrics.json が見つかりません。`experiment-run` を先に走らせてください」
     と伝えて止まる

3. **`scripts/compare_runs.py` を実行**:
   ```bash
   uv run python scripts/compare_runs.py <id1> <id2> [<id3> ...] [--out <name>] [--plot]
   ```
   - 出力: `docs/experiments/comparisons/<name>/comparison.md` (+ `--plot` 時は `der_box.png`, `rtf_bar.png`)
   - 評価条件 (split / collar / skip_overlap / n_speakers) が揃わない場合は script が
     warning ログを出すので、その内容をユーザーにも伝える

4. **生成された `comparison.md` を読み込み、観察事実を bullet で 1〜3 個提示**:
   - aggregate での DER / RTF の差分の方向 (どちらがどれだけ良い / 悪い)
   - per-meeting で最大差が出た meeting
   - 話者数推定誤り (predicted - reference) が顕著にずれている meeting

   断定を避け、**「観察」レベル**に留める。例:
   - 🟢 / 🔴 / 「勝ち」「負け」などの判定語は使わない
   - 「<id1> のほうが micro DER で 0.0003 低い」など、数値で淡々と

5. **次のアクションをユーザーに委ねる**:
   - 「考察は `docs/experiments/comparisons/<name>/comparison.md` を見て手動で追記してください」
   - 「本番昇格 (`feature/promote-*`) するかどうかは数値を見て判断してください」と促す
   - 自動で `experiments/<id>/notes.md` や `docs/experiments/<id>.md` を書き換えない

## やってはいけないこと

- どの実験が「勝ち」「失敗」「採用すべき」かを断定しない (観察事実のみ提示)
- `experiments/<id>/notes.md` や `docs/experiments/<id>.md` を勝手に書き換えない
- 評価条件 (split / collar など) が揃っていないのに警告を出さずに通さない
- `scripts/compare_runs.py` の責務 (テーブル生成・プロット) を skill 内で再実装しない
- 比較結果から「次にやること」を勝手に提案しない (ユーザーの考察待ち)

## 参考

- 実装本体: `scripts/compare_runs.py`
- 既存実験の metrics.json schema: `experiments/<id>/results/metrics.json` (`metrics` / `per_file` / `evaluation` セクション)
- 出力先 `docs/experiments/comparisons/` は Obsidian vault 内 (`docs/` symlink 経由)
- 関連 skill: `experiment-run` (個別実験の実行・記録)
