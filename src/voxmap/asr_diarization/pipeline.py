"""ASR × diarization 統合パイプライン (直列 / 並列 切替可)。

diarization (「誰がいつ」) と ASR (「何を」) を走らせ、`assign_speakers` で word↔speaker を
時間結合して `AttributedTranscript` を作る。

- ``mode="serial"``: diarization → ASR を順に実行 (wall ≒ 両者の和)
- ``mode="parallel"``: 2 スレッドで同時実行 (wall ≒ 両者の max。ただし同一 GPU を使う場合は
  競合で max まで縮まないことがある — 実測で確認する前提)

diarization と ASR は callable として注入する (DI)。diarization は `(audio, **kwargs) ->
Diarization`、ASR は `(audio) -> Transcript`。fusion は両モードで共有するので、直列版で
組んでおけば並列版は実行戦略だけ差し替わる。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from voxmap.asr_diarization.fusion import assign_speakers
from voxmap.types import AttributedTranscript, Audio, Diarization, Transcript

Mode = Literal["serial", "parallel"]


class _Diarize(Protocol):
    def __call__(self, audio: Audio, **kwargs: Any) -> Diarization: ...


class _ASR(Protocol):
    def __call__(self, audio: Audio) -> Transcript: ...


@dataclass(frozen=True, slots=True)
class ASRDiarizationResult:
    attributed: AttributedTranscript
    diarization: Diarization
    transcript: Transcript
    diarization_seconds: float
    asr_seconds: float
    fusion_seconds: float
    wall_seconds: float
    mode: Mode


class ASRDiarizationPipeline:
    def __init__(
        self,
        diarize: _Diarize,
        asr: _ASR,
        mode: Mode = "serial",
        fallback_speaker: str = "speaker_unknown",
    ) -> None:
        self.diarize = diarize
        self.asr = asr
        self.mode = mode
        self.fallback_speaker = fallback_speaker

    def __call__(self, audio: Audio, **diarize_kwargs: Any) -> ASRDiarizationResult:
        wall0 = time.perf_counter()
        if self.mode == "serial":
            diar, diar_s = _timed(lambda: self.diarize(audio, **diarize_kwargs))
            transcript, asr_s = _timed(lambda: self.asr(audio))
        elif self.mode == "parallel":
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_diar = ex.submit(lambda: _timed(lambda: self.diarize(audio, **diarize_kwargs)))
                f_asr = ex.submit(lambda: _timed(lambda: self.asr(audio)))
                diar, diar_s = f_diar.result()
                transcript, asr_s = f_asr.result()
        else:  # pragma: no cover - guarded by Literal
            raise ValueError(f"unknown mode: {self.mode}")

        t0 = time.perf_counter()
        attributed = assign_speakers(transcript, diar, fallback_speaker=self.fallback_speaker)
        fusion_s = time.perf_counter() - t0

        return ASRDiarizationResult(
            attributed=attributed,
            diarization=diar,
            transcript=transcript,
            diarization_seconds=diar_s,
            asr_seconds=asr_s,
            fusion_seconds=fusion_s,
            wall_seconds=time.perf_counter() - wall0,
            mode=self.mode,
        )


def _timed(fn: Any) -> tuple[Any, float]:
    t0 = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - t0
