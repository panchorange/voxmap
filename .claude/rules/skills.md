# skills

- `.claude/skills/setup-theme` — 新しい実験テーマの立ち上げ。`experiments/ analysis/ profiles/` それぞれに `<テーマ日付>_<テーマ名>/README.md` (各フォルダの役割 + テーマの主要指標・ゴール) を作り、`docs/theme/<theme>.md` に3者をつなぐ概要を書く。個別作成は experiment-design / analysis-design / profile-design
- `.claude/skills/design-lookup` — 設計質問時に `docs/` を参照
- `.claude/skills/experiment-design` — `experiments/<theme>/<日付>_<名前>/` 新規作成の定型作業
- `.claude/skills/experiment-run` — `experiments/<theme>/<id>/run.py` を実行し、metrics.json から notes/docs/<theme>/_index に結果を転記
- `.claude/skills/compare-runs` — 複数の `experiments/<theme>/<id>/` の metrics.json を読み、aggregate / per-meeting の DER・RTF・話者消失率・話者数推定誤り を markdown で比較出力 (`--plot` で box / bar chart も生成)
- `.claude/skills/profile-design` — `profiles/<theme>/<日付>_<名前>/` 新規作成の定型作業
- `.claude/skills/profile-run` — `profiles/<theme>/<id>/profile.py` を実行し、wall time / throughput / module breakdown を notes.md と docs/profiles/<theme>/ に転記
- `.claude/skills/analysis-design` — `analysis/<theme>/<日付>_<名前>/` (精度・データ特性の可視化/定量) 新規作成の定型作業。可視化部品は `src/voxmap/eval/visualize.py` を import する設計
- `.claude/skills/analysis-run` — `analysis/<theme>/<id>/analyze.py` (または薄い CLI `scripts/analyze_pipeline.py`) を実行し、cluster purity / 話者数推定誤り / 図の所見を notes.md・docs/analysis/<theme>/・_index に転記
- `.claude/skills/sync-check` — repo / Obsidian / `_index.md` / GCS (`gs://voxmap/`) の整合性チェック (`scripts/sync_check.py` のラッパー)。`make sync-check` 経由でも呼べる
- `.claude/skills/sync-results` — 単一の `experiments/<theme>/<id>/results/` ・ `profiles/<theme>/<id>/results/` ・ `analysis/<theme>/<id>/results/` を GCS と upload / download / list (`scripts/sync_results.py` のラッパー)。`experiment-run` / `profile-run` / `analysis-run` から呼ばれる
- `.claude/skills/paper-draft` — `paper/<日付>_<名前>/draft.md` を対話で埋める (思考整理・主張の裏付け・図選定)。清書の前段
- `.claude/skills/paper-write` — `paper/<id>/draft.md` から `<id>.tex` をセクション単位で生成し、同フォルダにPDF出力
- `.claude/skills/paper-review` — `paper/<id>/` の draft/knowleadge/tex を突き合わせてAIレビューし `reviewed_<timestamp>.md` を出力 (指摘のみ、書き換えない)
