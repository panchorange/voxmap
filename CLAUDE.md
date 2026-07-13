# voxmap

話者分離 (speaker diarization) のライブラリ兼、精度向上のための実験リポジトリ。
詳細は [README.md](README.md)、実験ワークフローは [experiments/README.md](experiments/README.md) を参照。
本書の内容はREADME.mdと整合性をとるようにする。

設計やアーキテクチャに関する質問が来たら、コードより先に `docs/design/` を読む。
無ければコードを読んで答える。

## ルールの所在

詳細ルールはトピック別に `.claude/rules/` に分割している (全て常時ロード)。

- `.claude/rules/repo-layout.md` — リポジトリ構成 + ドキュメントの場所
- `.claude/rules/development.md` — 開発ルール (Python/uv/ruff/mypy/make check/pre-commit)
- `.claude/rules/branching.md` — ブランチ命名 + 切り口の整理 + ADR
- `.claude/rules/skills.md` — skills 一覧
- `.claude/rules/gcs-layout.md` — GCS の結果保管レイアウト (`<kind>/<theme>/<id>/results/`) + 同期方法
- `.claude/rules/versioning.md` — SemVer 運用 (0系の扱い・MINOR/PATCH の判断) + CHANGELOG (Keep a Changelog) + リリースノートの位置づけ
