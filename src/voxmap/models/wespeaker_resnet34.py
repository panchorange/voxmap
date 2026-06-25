"""WeSpeaker ResNet34-LM — speaker embedding model (256-dim).

Vendored from pyannote.audio==4.0.4
  upstream:
    pyannote/audio/models/embedding/wespeaker/resnet.py    (ResNet, BasicBlock, TSTP)
    pyannote/audio/models/embedding/wespeaker/__init__.py  (BaseWeSpeakerResNet, WeSpeakerResNet34)
    pyannote/audio/models/blocks/pooling.py                (StatsPool)
  license:  Apache 2.0 (see LICENSE.WeSpeaker next to this file)
  reason:   Phase 2-1 vendor (see docs/design/decisions/2026-05-10_vendor_pyannote_models.md)

Only ResNet34 (BasicBlock) is vendored. ResNet18/50/.../293 and Bottleneck are dropped.
State-dict compatibility: layer names match upstream so weights from
`pyannote/wespeaker-voxceleb-resnet34-LM` load via `from_pyannote()`.

Architecture (16kHz mono, 80-mel fbank):
  waveform (B, 1, samples) →
    fbank (kaldi) → (B, T, 80) →
    Conv2d 1→32 → BN → ReLU →
    layer1 BasicBlock×3 (32ch)  → layer2 ×4 (64ch, s=2)
    layer3 ×6 (128ch, s=2)      → layer4 ×3 (256ch, s=2)
    TSTP (mean+std weighted by mask) → (B, 5120)
    Linear → (B, 256)  ← embedding
"""

from __future__ import annotations

from functools import partial
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio.compliance.kaldi as kaldi
from einops import rearrange


def _stats_pool(sequences: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    """Weighted mean+std along the last (frame) axis. Returns (batch, 2*features)."""
    weights = weights.unsqueeze(dim=1)  # (B, 1, T)
    v1 = weights.sum(dim=2) + 1e-8
    mean = torch.sum(sequences * weights, dim=2) / v1
    dx2 = torch.square(sequences - mean.unsqueeze(2))
    v2 = torch.square(weights).sum(dim=2)
    var = torch.sum(dx2 * weights, dim=2) / (v1 - v2 / v1 + 1e-8)
    std = torch.sqrt(var)
    return torch.cat([mean, std], dim=1)


class StatsPool(nn.Module):
    """Vendored from pyannote.audio.models.blocks.pooling.StatsPool."""

    def forward(
        self,
        sequences: torch.Tensor,
        weights: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if weights is None:
            mean = sequences.mean(dim=-1)
            std = sequences.std(dim=-1, correction=1)
            return torch.cat([mean, std], dim=-1)

        has_speaker_dimension = weights.dim() != 2
        if not has_speaker_dimension:
            weights = weights.unsqueeze(dim=1)  # (B, T) → (B, 1, T)

        _, _, num_frames = sequences.size()
        _, num_speakers, num_weights = weights.size()
        if num_frames != num_weights:
            weights = F.interpolate(weights, size=num_frames, mode="nearest")

        output = torch.stack(
            [_stats_pool(sequences, weights[:, sp, :]) for sp in range(num_speakers)],
            dim=1,
        )
        return output if has_speaker_dimension else output.squeeze(dim=1)


class TSTP(nn.Module):
    """Temporal statistics pooling — concatenate mean and std (weighted)."""

    def __init__(self, in_dim: int = 0) -> None:
        super().__init__()
        self.in_dim = in_dim
        self.stats_pool = StatsPool()

    def forward(self, features: torch.Tensor, weights: torch.Tensor | None = None) -> torch.Tensor:
        # features: (B, channel_dim, freq, frames) → flatten freq×channel
        features = rearrange(
            features,
            "batch dimension channel frames -> batch (dimension channel) frames",
        )
        result: torch.Tensor = self.stats_pool(features, weights=weights)
        return result

    def get_out_dim(self) -> int:
        return self.in_dim * 2


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, in_planes: int, planes: int, stride: int = 1) -> None:
        super().__init__()
        self.stride = stride
        self.conv1 = nn.Conv2d(
            in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False
        )
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)

        self.shortcut: nn.Module = nn.Sequential()
        if stride != 1 or in_planes != self.expansion * planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(
                    in_planes,
                    self.expansion * planes,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                ),
                nn.BatchNorm2d(self.expansion * planes),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = out + self.shortcut(x)
        return F.relu(out)


class ResNet(nn.Module):
    """Bare ResNet body with BasicBlock — no Bottleneck variant."""

    def __init__(
        self,
        num_blocks: list[int],
        m_channels: int = 32,
        feat_dim: int = 80,
        embed_dim: int = 256,
        two_emb_layer: bool = False,
    ) -> None:
        super().__init__()
        self.in_planes = m_channels
        self.feat_dim = feat_dim
        self.embed_dim = embed_dim
        self.stats_dim = (feat_dim // 8) * m_channels * 8
        self.two_emb_layer = two_emb_layer

        self.conv1 = nn.Conv2d(1, m_channels, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(m_channels)
        self.layer1 = self._make_layer(m_channels, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(m_channels * 2, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(m_channels * 4, num_blocks[2], stride=2)
        self.layer4 = self._make_layer(m_channels * 8, num_blocks[3], stride=2)

        self.pool = TSTP(in_dim=self.stats_dim * BasicBlock.expansion)
        self.pool_out_dim = self.pool.get_out_dim()
        self.seg_1 = nn.Linear(self.pool_out_dim, embed_dim)
        self.seg_bn_1: nn.Module
        self.seg_2: nn.Module
        if self.two_emb_layer:
            self.seg_bn_1 = nn.BatchNorm1d(embed_dim, affine=False)
            self.seg_2 = nn.Linear(embed_dim, embed_dim)
        else:
            self.seg_bn_1 = nn.Identity()
            self.seg_2 = nn.Identity()

    def _make_layer(self, planes: int, num_blocks: int, stride: int) -> nn.Sequential:
        strides = [stride] + [1] * (num_blocks - 1)
        layers: list[nn.Module] = []
        for s in strides:
            layers.append(BasicBlock(self.in_planes, planes, s))
            self.in_planes = planes * BasicBlock.expansion
        return nn.Sequential(*layers)

    def forward(
        self, fbank: torch.Tensor, weights: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # fbank: (B, T, F) → (B, 1, F, T) for Conv2d
        fbank = fbank.permute(0, 2, 1).unsqueeze_(1)
        out = F.relu(self.bn1(self.conv1(fbank)))
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)

        stats = self.pool(out, weights=weights)
        embed_a = self.seg_1(stats)
        if self.two_emb_layer:
            tmp = F.relu(embed_a)
            tmp = self.seg_bn_1(tmp)
            embed_b = self.seg_2(tmp)
            return embed_a, embed_b
        return torch.tensor(0.0), embed_a


def ResNet34(feat_dim: int = 80, embed_dim: int = 256, two_emb_layer: bool = False) -> ResNet:  # noqa: N802
    """ResNet34 builder (BasicBlock counts [3, 4, 6, 3])."""
    return ResNet([3, 4, 6, 3], feat_dim=feat_dim, embed_dim=embed_dim, two_emb_layer=two_emb_layer)


class WeSpeakerResNet34(nn.Module):
    """End-to-end speaker embedding model: waveform → fbank → ResNet34 → 256-dim.

    Wraps:
      - kaldi fbank computation (with WeSpeaker's specific settings)
      - the vendored ResNet34 body

    State-dict layout matches `pyannote/wespeaker-voxceleb-resnet34-LM`:
      `resnet.<name>` for ResNet body parameters.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        num_mel_bins: int = 80,
        frame_length: int = 25,
        frame_shift: int = 10,
        dither: float = 0.0,
        window_type: str = "hamming",
        use_energy: bool = False,
    ) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self.num_mel_bins = num_mel_bins
        self.frame_length = frame_length
        self.frame_shift = frame_shift
        self.dither = dither
        self.window_type = window_type
        self.use_energy = use_energy

        self._fbank = partial(
            kaldi.fbank,
            num_mel_bins=num_mel_bins,
            frame_length=frame_length,
            round_to_power_of_two=True,
            frame_shift=frame_shift,
            snip_edges=True,
            dither=dither,
            sample_frequency=sample_rate,
            window_type=window_type,
            use_energy=use_energy,
        )

        self.resnet = ResNet34(feat_dim=num_mel_bins, embed_dim=256, two_emb_layer=False)

    @property
    def dimension(self) -> int:
        return self.resnet.embed_dim

    @property
    def metric(self) -> str:
        return "cosine"

    @property
    def min_num_samples(self) -> int:
        # roughly 0.5s — enough to extract a stable fbank window
        return 8000

    def compute_fbank(self, waveforms: torch.Tensor) -> torch.Tensor:
        """waveforms: (B, 1, samples) → fbank (B, T, num_mel_bins).

        WeSpeaker scales waveform by 1<<15 (i.e., assumes int16-domain). FFT
        runs on CPU when input is on MPS (MPS FFT is incomplete in torch 2.x).
        """
        waveforms = waveforms * (1 << 15)
        device = waveforms.device
        fft_device = torch.device("cpu") if device.type == "mps" else device
        features: torch.Tensor = torch.vmap(self._fbank)(waveforms.to(fft_device)).to(device)
        return features - torch.mean(features, dim=1, keepdim=True)

    def forward(self, waveforms: torch.Tensor, weights: torch.Tensor | None = None) -> torch.Tensor:
        """waveforms: (B, 1, samples), weights: (B, T) optional → embedding (B, 256)."""
        fbank = self.compute_fbank(waveforms)
        emb: torch.Tensor = self.resnet(fbank, weights=weights)[1]
        return emb

    @classmethod
    def from_pyannote(
        cls,
        model_id: str = "pyannote/wespeaker-voxceleb-resnet34-LM",
        token: str | None = None,
        cache_dir: str | None = None,
    ) -> WeSpeakerResNet34:
        """Bootstrap weights from pyannote checkpoint (one-time bridge)."""
        from pyannote.audio import Model

        original = Model.from_pretrained(model_id, token=token, cache_dir=cache_dir, strict=False)
        if original is None:
            raise RuntimeError(f"pyannote.Model.from_pretrained({model_id!r}) returned None")

        hp: Any = original.hparams
        instance = cls(
            sample_rate=hp.sample_rate,
            num_mel_bins=hp.num_mel_bins,
            frame_length=int(hp.frame_length),
            frame_shift=int(hp.frame_shift),
            dither=hp.dither,
            window_type=hp.window_type,
            use_energy=hp.use_energy,
        )
        # copy only resnet.* keys — drop pyannote.Model-specific buffers
        own_keys = set(instance.state_dict().keys())
        filtered = {k: v for k, v in original.state_dict().items() if k in own_keys}
        missing, unexpected = instance.load_state_dict(filtered, strict=False)
        if missing or unexpected:
            raise RuntimeError(
                f"unexpected state_dict mismatch — missing={missing!r}, unexpected={unexpected!r}"
            )
        instance.eval()
        return instance
