"""Segmentation stage — chunk-based powerset diarization.

Distinct from `voxmap.vad` (frame-level speech/non-speech). This stage outputs
per-chunk per-frame multilabel speaker activity for the downstream pipeline.
"""
