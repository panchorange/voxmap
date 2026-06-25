---
name: paper-draft
description: 論文 (paper/<日付>_<名前>/) の下書きを、ユーザーと対話的に情報収集しながら作る。実験データの事実確認・主張の裏付けリンク・必要な図の選定までを draft.md にまとめる。清書 (paper-write) の前段。
---

# paper-draft

draft.md を対話で埋めていく skill。主張は必ず実験データで裏付ける。

## 手順

1. `paper/<YYYY-MM-DD>_<name>/` がなければ作成。`knowleadge.md` と `draft.md` を用意
2. knowleadge.md に主張で使う数値を metrics.json から転記し、出典を併記。ユーザーと数値を突き合わせる
3. draft.md を対話で埋める:
   - §0.1 one-liner
   - §0.2 貢献 (裏付けリンク必須。リンクなしは「根拠未確認」と明記)
   - §0.3 open questions (over-claim しそうな箇所を正直に書く)
   - §用語集 (清書前に表記を確定)
   - §構成 (セクション表。Abstract/貢献文は「最後に確定」とメモ)
   - §主要結果テーブル素材 (各セルに出典リンク)
4. 必要な図を選定。既存 analysis/profiles の図を流用できないか先に確認。新規作図は「図TODO」として残す
5. draft が埋まったら「確認・修正してください。固まったら paper-write を起動します」と伝える

## やってはいけないこと

- 実験データにない数値を書かない
- 裏付けリンクなしの主張を断定で書かない
- ユーザー確認なしに paper-write へ進まない
