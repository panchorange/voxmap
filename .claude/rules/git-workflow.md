# git ワークフロー

- **commit と PR 作成は人間が行う**。AI (Claude) は変更を加えるところまで。コミットや
  PR の発行はユーザーに委ねる (求められた場合のみ補助する)。
- AI が commit する場合でも、**`Co-Authored-By` などの AI 署名トレーラーを付けない**。
  コミットメッセージに Claude / AI の共著者情報を入れない。
- PR 本文にも AI 生成を示すフッター (`Generated with Claude Code` 等) を入れない。
