from pathlib import Path

import torch
import torchaudio

from voxmap.types import Audio

DEFAULT_SAMPLE_RATE = 16_000


def load_audio(path: str | Path, target_sample_rate: int = DEFAULT_SAMPLE_RATE) -> Audio:
    waveform, sample_rate = torchaudio.load(str(path))

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    if sample_rate != target_sample_rate:
        resampler = torchaudio.transforms.Resample(sample_rate, target_sample_rate)
        waveform = resampler(waveform)
        sample_rate = target_sample_rate

    return Audio(waveform=waveform.to(torch.float32), sample_rate=sample_rate)
