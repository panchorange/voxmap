# 開発ルール

- `.claude/worktrees/` は使わない (作業は main repo `/Users/yamaguchifumiaki/research/voxmap/` で行う。worktree で起動された場合は main repo にコピーしてから作業)
- Python 3.12 / uv / ruff / mypy(strict) / pre-commit
- `make check` (lint + typecheck) と `make test` を変更後に走らせる
- pre-commitが入っているので commit時に自動チェックされる
- ベースラインは pyannote / wespeaker を参考にする方針 (車輪の再発明はしない)
- 評価は **pyannote.metrics + 自前指標 (話者消失率/混同行列/レイテンシ) のハイブリッド**
- 実験管理は当面 `metrics.json + notes.md` の手書き運用。実験10超でwandb等を検討
- src/ の開発に必要な場合を除き、uv addする際は --devで開発グループにライブラリを追加すること
