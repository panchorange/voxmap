# バージョニングとリリース

公開 repo (`voxmap`) のバージョン付け・変更履歴・リリースの運用ルール。

## SemVer (Semantic Versioning)

バージョンは `MAJOR.MINOR.PATCH` (タグは `vX.Y.Z`)。`pyproject.toml` の `version` が正。

| 部分 | 上げる条件 | 例 |
|---|---|---|
| **MAJOR** | 後方互換を壊す変更 (公開 API シグネチャの変更・削除、設定ファイルの非互換) | `load_diarization31_pipeline` の引数削除・改名 |
| **MINOR** | 後方互換を保った機能追加 | 新 CLI オプション、デフォルト付きの新パラメータ、studio の新機能 |
| **PATCH** | 後方互換のバグ修正のみ | 例外処理の修正、計算誤りの是正 |

### 各セグメントは「数値」であって小数ではない

`.` は区切り文字。カウンタは独立して増える。**`0.9.0` の次は `0.10.0`** (`0.9.0` より新しい)。
`0.10.1`・`0.100.0` も正常。文字列比較すると誤るので必ず数値として扱う。

```
0.1.0 → 0.2.0 → ... → 0.9.0 → 0.10.0 → 0.11.0 → ... → 1.0.0
```

### 0系 (`0.y.z`) の扱い

`0.y.z` は「公開 API がまだ固まっていない」意思表示。**0系の間は破壊的変更を入れても MINOR up でよい**
運用とする。voxmap は公開初期なので当面 0系で回す。API が安定し「もう気軽に壊さない」と宣言できる
タイミングで `1.0.0` に上げる (厳密な条件はなく、互換維持の責任を負う覚悟ができた時)。

### 判断が迷うとき

- 機能追加とバグ修正が混ざる → 上位 (MINOR) を優先。
- デフォルト値が変わり出力が変わるが API は互換 (例: `min_duration_on` の 0.0→0.3) → 0系では MINOR。
  CHANGELOG の `Changed` に明記し、リリースノートの「アップグレード注意」で戻し方を案内する。

## CHANGELOG.md ([Keep a Changelog] 形式)

ルート `CHANGELOG.md` が**恒久的な変更履歴の正**。全バージョン分を累積する。

- 見出しは `## [X.Y.Z] - YYYY-MM-DD` の逆時系列 (新しい方が上)。
- 最上部に `## [Unreleased]` を置き、次リリースまでの変更を先に積む。リリース時にバージョン番号へ確定。
- 変更は **`Added` / `Changed` / `Deprecated` / `Removed` / `Fixed` / `Security`** に分類。
- 末尾に各バージョンの GitHub compare リンクを列挙。
- 読者は開発者・依存先。簡潔な事実の箇条書きで書く。

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/

## リリースノート (GitHub Release 本文)

GitHub の Release ページ本文が「利用者向けのお知らせ」。**リポジトリに常設ファイルとして置かない。**

- 実体は GitHub Release ページ (GitHub 側に恒久保存される)。
- `gh release create` に渡すための一時ファイル (例 `release_notes.md`) を作ってもよいが、
  **commit せず使い捨てる** (発行後に削除、または最初から追跡しない)。
- 内容は CHANGELOG の該当セクションを土台に、ハイライト・使い方・移行ガイドを利用者目線で足す。
  CHANGELOG と完全重複させない (CHANGELOG=生ログ、Release=お知らせ、で役割を分ける)。

## リリース手順 (commit / tag / Release 発行は人間が行う — [git-workflow] 準拠)

AI はファイル変更・バージョン更新・CHANGELOG 追記まで。以下はユーザーが実行する。

```bash
# 1. バージョンを確定 (pyproject.toml) + CHANGELOG の Unreleased を確定済みにする (AI が実施)
# 2. commit → tag → push
git commit -m "release: vX.Y.Z"
git tag vX.Y.Z
git push origin <branch> --tags
# 3. GitHub Release (本文は使い捨ての notes ファイル or CHANGELOG セクションを流用)
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <tmp>
```

初回リリースにタグが無い場合、compare リンクを機能させるため遡ってタグを打つ
(`git tag v0.1.0 <commit>`)。

[git-workflow]: ./git-workflow.md

## 関連

- `.claude/rules/git-workflow.md` — commit/tag/PR は人間、AI 署名を付けない
- `.claude/rules/branching.md` — `feature/promote-*` (本番 config 昇格) は ADR 必須
