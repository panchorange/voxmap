"""SincNet block — learnable bandpass filter front-end for raw waveforms.

Vendored verbatim from pyannote.audio==4.0.4
  upstream: pyannote/audio/models/blocks/sincnet.py
  license:  MIT (see LICENSE.pyannote at this directory's parent)
  reason:   Phase 2-1 vendor (see docs/design/decisions/2026-05-10_vendor_pyannote_models.md)

State-dict compatibility: layer names and shapes are kept identical to upstream
so weights from `pyannote/segmentation-3.0` checkpoints load via copy_().
"""

from __future__ import annotations

from functools import lru_cache

import torch
import torch.nn as nn
import torch.nn.functional as F
from asteroid_filterbanks import Encoder, ParamSincFB
from pyannote.audio.utils.receptive_field import (
    multi_conv_num_frames,
    multi_conv_receptive_field_center,
    multi_conv_receptive_field_size,
)


class SincNet(nn.Module):
    def __init__(self, sample_rate: int = 16000, stride: int = 1) -> None:
        super().__init__()

        if sample_rate != 16000:
            raise NotImplementedError("SincNet only supports 16kHz audio for now.")

        self.sample_rate = sample_rate
        self.stride = stride

        self.wav_norm1d = nn.InstanceNorm1d(1, affine=True)

        self.conv1d = nn.ModuleList()
        self.pool1d = nn.ModuleList()
        self.norm1d = nn.ModuleList()

        self.conv1d.append(
            Encoder(
                ParamSincFB(
                    80,
                    251,
                    stride=self.stride,
                    sample_rate=sample_rate,
                    min_low_hz=50,
                    min_band_hz=50,
                )
            )
        )
        self.pool1d.append(nn.MaxPool1d(3, stride=3, padding=0, dilation=1))
        self.norm1d.append(nn.InstanceNorm1d(80, affine=True))

        self.conv1d.append(nn.Conv1d(80, 60, 5, stride=1))
        self.pool1d.append(nn.MaxPool1d(3, stride=3, padding=0, dilation=1))
        self.norm1d.append(nn.InstanceNorm1d(60, affine=True))

        self.conv1d.append(nn.Conv1d(60, 60, 5, stride=1))
        self.pool1d.append(nn.MaxPool1d(3, stride=3, padding=0, dilation=1))
        self.norm1d.append(nn.InstanceNorm1d(60, affine=True))

    @lru_cache  # noqa: B019
    def num_frames(self, num_samples: int) -> int:
        kernel_size = [251, 3, 5, 3, 5, 3]
        stride = [self.stride, 3, 1, 3, 1, 3]
        padding = [0, 0, 0, 0, 0, 0]
        dilation = [1, 1, 1, 1, 1, 1]
        return multi_conv_num_frames(
            num_samples,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
        )

    def receptive_field_size(self, num_frames: int = 1) -> int:
        kernel_size = [251, 3, 5, 3, 5, 3]
        stride = [self.stride, 3, 1, 3, 1, 3]
        padding = [0, 0, 0, 0, 0, 0]
        dilation = [1, 1, 1, 1, 1, 1]
        return multi_conv_receptive_field_size(
            num_frames,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
        )

    def receptive_field_center(self, frame: int = 0) -> int:
        kernel_size = [251, 3, 5, 3, 5, 3]
        stride = [self.stride, 3, 1, 3, 1, 3]
        padding = [0, 0, 0, 0, 0, 0]
        dilation = [1, 1, 1, 1, 1, 1]
        return multi_conv_receptive_field_center(
            frame,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
        )

    def forward(self, waveforms: torch.Tensor) -> torch.Tensor:
        """waveforms: (batch, channel, sample) → (batch, 60, frame)."""
        outputs: torch.Tensor = self.wav_norm1d(waveforms)

        for c, (conv1d, pool1d, norm1d) in enumerate(
            zip(self.conv1d, self.pool1d, self.norm1d, strict=True)
        ):
            outputs = conv1d(outputs)
            if c == 0:
                # https://github.com/mravanelli/SincNet/issues/4
                outputs = torch.abs(outputs)
            outputs = F.leaky_relu(norm1d(pool1d(outputs)))

        return outputs
