---
name: paper-review
description: paper/<id>/ の draft.md・knowleadge.md・tex を突き合わせてAIレビューし、指摘を paper/<id>/reviewed_YYYY-MM-DD-HHMMSS.md に出力する。AIは断定で書き換えず、観点ごとに指摘リストを出してユーザーが判断する。
---

# paper-review

ソロ研究の論文を、共著者代わりにAIがレビューする skill。
**AIは勝手に書き換えない。観点ごとに指摘を出し、判断はユーザーに委ねる** (compare-runs と同じ思想)。

## 手順

1. レビュー対象を読む: `paper/<id>/` の `draft.md`, `knowleadge.md`, `*.tex` (あれば)
2. 下記11観点でチェックし、指摘を集める
3. `paper/<id>/reviewed_<YYYY-MM-DD-HHMMSS>.md` に出力 (タイムスタンプは `date +%Y-%m-%d-%H%M%S`)
4. ユーザーに「レビューを出力しました。対応は判断してください」と伝える。**自動で本文を直さない**

## レビュー観点

**最優先 (数値・主張の穴)**
1. **数値照合**: 本文・abstract・表の数値が knowleadge.md / metrics.json と一致するか。
   出力は**論文のセクションごとに小見出しを立て、数字1つ1つを実験結果に対応づけたチェックボックス箇条書き**にする (人間が目視確認しやすい形)。一致/不一致の判定 (OK / 不一致 / 出典不明) と、一次ソース (`experiments/<id>/results/metrics.json` 等の具体パス) を必ず添える。形式例:
   ```
   ## Abstract
   - [ ] DER 0.080 (VoxConverse recovered) : OK — experiments/2026-05-21_voxconverse-relative-mcs-f001/results/metrics.json (der_micro 0.0795)
   - [ ] 12.2x speedup : OK — knowleadge.md §1 (AMI RTF 0.061→0.005)
   - [ ] DER 0.075→0.113 : 不一致 — metrics.json は 0.0752→0.1127 (本文丸めは可だが要確認)
   ## §IV Recipe
   - [ ] ...
   ```
   セクション順 (Abstract → 各 §) に並べ、漏れなく全数字を拾う。
2. **主張 ⊆ 根拠**: 各主張に裏付けリンクがあるか。「ほぼ維持」「数倍」等の定量語が数値と合うか
3. **over-claim**: draft §0.3 open questions が本文で正しく限定されているか

**評価の厳密さ**
4. **評価条件の明示**: collar / skip_overlap / split / device が書かれているか。データセット間の条件差に注記があるか
5. **比較の公平性**: ベースラインが妥当か。confound (デバイス混在RTF、モデル換装込みspeedup) に脚注があるか
6. **新規性の位置づけ**: 既存手法との差分を正直に書けているか

**完成度**
7. **論理の流れ**: motivation→problem→diagnosis→solution→validation が繋がるか。前後の矛盾
8. **Limitations の正直さ**: 弱点が隠されていないか
9. **想定査読コメント**: draft §0.4 の反論メモが本文で先回りされているか
10. **用語・表記の一貫性**: glossary 準拠、略語の初出定義

**引用の正確性**
11. **引用整合性**: 本文中の `\cite{}` キーがすべて `\bibitem` に対応しているか (dangling citation)。逆に `\bibitem` があるのに未引用の文献がないか。本文で「〇〇が報告した」と書いた内容が cited source の実際の記述・数値と一致するか。とくに数値引用 (Figure/Table 番号含む) はズレに注意。一致しない場合は「出典と齟齬あり: <本文の主張> ← 実際は <出典の記述>」の形で指摘する。knowleadge.md に cited source の要約がある場合はそれを照合。ない場合は「出典内容が knowleadge.md に記録されていないため照合不能」と明記し、ユーザーに手動確認を促す。

    さらに、**引用文献ごとにチェックボックス箇条書き**を出力し、人間が原典を確認できるようにする。各文献について:
    - 論文/原典への**直リンク (URL/DOI)** を載せる。
    - リンクが取れない場合は、**検索でその1本に特定できる検索クエリ** (著者+正確なタイトル+会議/誌名+年) を載せる。
    - **knowleadge.md に出典内容の要約があるか**を明記 (あれば照合済/なければ手動確認要)。
    形式例:
    ```
    ## 引用チェック
    - [ ] `powerset` Plaquet & Bredin, "Powerset multi-class cross entropy loss for neural speaker diarization", Interspeech 2023
      - link: https://www.isca-archive.org/interspeech_2023/plaquet23_interspeech.html
      - knowleadge: 要約なし → 内容は手動確認
    - [ ] `wespeaker` S. Wang et al., "Advancing speaker embedding learning: Wespeaker toolkit…", Speech Communication 162 (2024)
      - link 取得不可 → 検索: "Wespeaker toolkit Shuai Wang Speech Communication 2024"
      - knowleadge: 要約なし → 手動確認
    ```

## 出力フォーマット (reviewed_*.md)

観点ごとにセクションを立て、各指摘を:
- **深刻度** (blocker / major / minor)
- **箇所** (ファイル:行 または セクション名)
- **指摘内容**
- **提案** (どう直すかの案。断定でなく選択肢)

で列挙。最後に「対応必須 (blocker/major)」のサマリを置く。

ただし**観点1 (数値照合) と観点11 (引用チェック) は、上記の指摘リストとは別に、人間が確認作業に使えるチェックボックス箇条書きセクションを必ず設ける** (各観点の説明にある形式例に従う)。指摘 (深刻度つき) は問題のある項目だけ、チェックボックスは全項目を網羅する、と役割を分ける。

## やってはいけないこと

- 本文・tex を自動で書き換えない (指摘のみ)
- 「合格/不合格」の総合判定を断定しない (材料を出す)
- knowleadge.md にない数値で「正しい値」を主張しない (照合のみ。出典が無い数値は「出典不明」と指摘)
- cited source の内容が knowleadge.md に記録されていない場合、AIが推測で「正しい内容」を断定しない (「照合不能、手動確認を」に留める)
