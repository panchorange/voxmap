---
name: paper-write
description: paper/<id>/draft.md を元に <id>.tex をセクション単位で生成し、同フォルダにPDFを出力する。既存 tex の修正→再コンパイルにも使う。
---

# paper-write

## 2つのモード

**A: draft → tex + PDF**
1. draft.md の構成・用語集・主張が固まっているか確認。不十分なら paper-draft を先に
2. レイアウトをユーザーに確認 (1カラム / 2カラム、投稿先クラス)。指定がなければ聞いてから書く
3. セクション単位で tex を生成 → ユーザー確認 → 次へ (OK が出るまで進まない)
3. 技術セクション (Method / Experiments / Discussion) を先に書き、Abstract/Introduction の貢献文は最後
4. 数値は draft.md / knowleadge.md から転記。新しい数値を作らない
5. 全セクション完了後に通しチェック (用語・数値・論旨)
6. `xelatex -output-directory "paper/<id>/" "paper/<id>/<id>.tex"` でPDF生成

**B: tex 修正 → PDF 再生成**
- ユーザー修正後に上記コマンドを実行するだけ
