# 開発ルール

- `.claude/worktrees/` は使わない (作業は main repo `/Users/yamaguchifumiaki/research/voxmap/` で行う。worktree で起動された場合は main repo にコピーしてから作業)
- Python 3.12 / uv / ruff / mypy(strict) / pre-commit
- `make check` (lint + typecheck) と `make test` を変更後に走らせる
- pre-commitが入っているので commit時に自動チェックされる
- ベースラインは pyannote / wespeaker を参考にする方針 (車輪の再発明はしない)
- 評価は **pyannote.metrics + 自前指標 (話者消失率/混同行列/レイテンシ) のハイブリッド**
- 実験管理は当面 `metrics.json + notes.md` の手書き運用。実験10超でwandb等を検討
- src/ の開発に必要な場合を除き、uv addする際は --devで開発グループにライブラリを追加すること

## CLI と GUI (studio) の整合

- **分離エンジンは `Diarization31Pipeline` (`load_diarization31_pipeline`) の一系統のみ**。
  CLI (`scripts/diarize.py` → `voxmap.pipeline.build_pipeline`) と GUI
  (`apps/studio/backend/app/diarize.py`) は必ず同じこれを通す。
  第二のパイプライン実装・ファサードを作らない (過去に CLI 専用の `DefaultPipeline` が
  未結線のまま公開され Issue #1 の TypeError を招いた。
  ADR: `docs/design/decisions/2026-07-07_cli-pipeline-align-diarization31.md`)
- `load_diarization31_pipeline` の引数を追加・変更したら、**CLI 側
  (`src/voxmap/pipeline/builder.py` + `configs/pipeline/baseline.yaml`) と studio 側
  (`apps/studio/backend/app/diarize.py` + `app/config.yaml`) の両方の config マッピングを
  同じ変更で更新する** (片方だけ追従漏れするとサイレントに挙動が割れる)
- README のクイックスタート (CLI コマンド・Python 例) は変更後に**実際に実行して**確認する。
  ドキュメントに書いた経路は動く経路であること
