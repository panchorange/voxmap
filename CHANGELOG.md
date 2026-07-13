# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/panchorange/voxmap/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/panchorange/voxmap/releases/tag/v0.2.0
