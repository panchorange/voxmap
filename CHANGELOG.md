# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- voxmap-studio: テーマ `Yell` を追加。夏のエールビールをモチーフにした淡いクリーム地 +
  琥珀オレンジの差し色で、余白には炭酸の泡がゆっくり立ちのぼる (`prefers-reduced-motion`
  時はアニメーションレイヤーごと非表示)。

### Changed
- voxmap-studio: テーマ `Game Boy` / `Brown` / `Black Diamond` をテーマ選択プルダウンから
  非表示にした。**実装 (CSS ブロック) は残してある**ので、既にそれらを選んでいる場合は
  引き続き有効 (その間だけプルダウンにも表示される)。

## [0.2.2] - 2026-07-31

### Fixed
- voxmap-studio: 公開前 (repo 改名前) の studio が `tool: "speaker-diarization-studio"` で
  書き出した途中保存 json (savepoint) を読み込めず、エラーも出ないまま無反応になる不具合を
  修正。読み込み時は現行名 `voxmap-studio` と旧名の両方を受け付ける (書き出しは現行名のみ)。
  `integrity` ハッシュは `fileId + segments` から計算し `tool` を含まないため、旧名 json でも
  改変警告 (tampered) は出ない。
- voxmap-studio: 読み込めなかった json が黙って無視されていたのをやめ、通知バナーに拒否理由
  (JSON として不正 / `tool` が非対応 — 実際の値を表示 / `segments` が配列でない) と読み込みに
  必要な条件を表示するようにした。i18n (JA/EN) 込み。

## [0.2.1] - 2026-07-24

### Fixed
- voxmap-studio: 波形の早送り・高速再生 (1.25x/1.5x) で再生した区間が「聞いた
  (heard)」としてカウントされず、`C` キーでの確認 (confirm) が拒否される不具合を修正。
  `coverageStore.mark()` が `rate > 1` の再生を丸ごとカバレッジ対象から除外していたのが
  原因 (シーク跨ぎの除外ロジックは意図通りのため維持)。

## [0.2.0] - 2026-07-13

### Added
- Short-segment suppression (`min_duration_on`) in `Diarization31Pipeline` /
  `load_diarization31_pipeline`: drops isolated very-short hypothesis segments
  (a common false-alarm signal). Configurable via `min_duration_on` in
  `configs/pipeline/baseline.yaml` and the studio backend config, range
  `[0.1, 1.0]` seconds or `0.0` to disable.
- Per-call override of `min_duration_on` on `Diarization31Pipeline.__call__`.
- voxmap-studio: a "Drop <" selector in the header (OFF / 0.1s–1.0s) to override
  the suppression threshold per diarization run, wired through the
  `/api/diarize` endpoint (with validation) and the frontend. i18n (JA/EN) included.

### Changed
- Default diarization output now applies `min_duration_on = 0.3` (previously no
  short-segment suppression). This changes hypothesis segments for the default
  config. Set `min_duration_on: 0.0` in your pipeline config to restore the old
  behavior.

[Unreleased]: https://github.com/panchorange/voxmap/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/panchorange/voxmap/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/panchorange/voxmap/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/panchorange/voxmap/releases/tag/v0.2.0
