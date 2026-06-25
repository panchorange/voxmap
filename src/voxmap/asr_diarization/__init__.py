"""ASR × diarization の統合: 「誰がいつ」(Diarization) と「何を」(Transcript) を
時間で突き合わせ、speaker-attributed transcript (AttributedTranscript) を作る。

- `fusion.assign_speakers` — word↔speaker を時間 overlap で割り当てる純関数
- `pipeline.ASRDiarizationPipeline` — diarization と ASR を走らせて fusion を適用する
  統合パイプライン。`mode="serial"` (直列) / `"parallel"` (並列) を切替可能で、
  どちらも同じ fusion を共有する。
"""

from voxmap.asr_diarization.fusion import assign_speakers
from voxmap.asr_diarization.pipeline import ASRDiarizationPipeline

__all__ = ["ASRDiarizationPipeline", "assign_speakers"]
