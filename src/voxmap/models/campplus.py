"""CAM++ — speaker embedding model (512-dim).

Vendored from WeSpeaker (wenet-e2e/wespeaker)
  upstream:
    wespeaker/models/campplus.py        (CAMPPlus, FCM, BasicResBlock, CAM*, TDNN*)
    wespeaker/models/pooling_layers.py  (TSTP)
  license:  Apache 2.0 (see LICENSE.WeSpeaker next to this file)
  reference paper:
    Wang et al., "CAM++: A Fast and Efficient Network for Speaker Verification
    Using Context-Aware Masking", arXiv:2303.00332

Adaptation notes:
  - TSTP is replaced with a weight-aware variant matching `WeSpeakerResNet34`'s
    StatsPool (frame-level mask interpolation + weighted mean/std). TSTP has
    no learnable parameters, so `avg_model.pt` state_dict loads as-is.
  - End-to-end wrapper `WeSpeakerCAMPlus` adds kaldi-fbank front-end and
    exposes the same interface as `WeSpeakerResNet34` (dimension / metric /
    min_num_samples / forward(waveforms, weights)) so it plugs into
    `voxmap.embedding.wespeaker_emb.WeSpeakerEmbedder` unchanged.

Architecture (16kHz mono, 80-mel fbank):
  waveform (B, 1, samples) →
    fbank (kaldi) → (B, T, 80) →
    FCM head → (B, 320, T)
    TDNN (stride=2) → (B, 128, T/2)
    CAMDenseTDNNBlock×3 (with TransitLayer in between)
    TSTP (mean+std weighted by mask) → (B, 2*channels)
    DenseLayer → (B, 512)  ← embedding
"""

from __future__ import annotations

from collections import OrderedDict
from functools import partial
from pathlib import Path
from typing import Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio.compliance.kaldi as kaldi


def _stats_pool(sequences: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    """Weighted mean+std along the last (frame) axis. Returns (batch, 2*features)."""
    weights = weights.unsqueeze(dim=1)  # (B, 1, T)
    v1 = weights.sum(dim=2) + 1e-8
    mean = torch.sum(sequences * weights, dim=2) / v1
    dx2 = torch.square(sequences - mean.unsqueeze(2))
    v2 = torch.square(weights).sum(dim=2)
    # v1 - v2/v1 は重み付き分散の Bessel 補正項（重みが 0/1 のとき通常の n-1 に一致）
    var = torch.sum(dx2 * weights, dim=2) / (v1 - v2 / v1 + 1e-8)
    std = torch.sqrt(var)
    return torch.cat([mean, std], dim=1)


class TSTP(nn.Module):
    """Temporal statistics pooling — weighted mean+std concatenation.

    Falls back to unweighted (= original WeSpeaker TSTP) when `weights is None`,
    so state_dict from `avg_model.pt` (trained without masks) loads unchanged.
    """

    def __init__(self, in_dim: int = 0) -> None:
        super().__init__()
        self.in_dim = in_dim

    def forward(self, x: torch.Tensor, weights: torch.Tensor | None = None) -> torch.Tensor:
        # x: (B, C, T)
        if weights is None:
            mean = x.mean(dim=-1).flatten(start_dim=1)
            std = torch.sqrt(torch.var(x, dim=-1) + 1e-7).flatten(start_dim=1)
            return torch.cat([mean, std], dim=1)

        if weights.dim() == 2:
            weights = weights.unsqueeze(dim=1)  # (B, T) → (B, 1, T)
        _, _, num_frames = x.size()
        _, _, num_weights = weights.size()
        if num_frames != num_weights:
            # マスクと fbank のフレーム数が異なる場合に補間（セグメンタの fps 依存）
            weights = F.interpolate(weights, size=num_frames, mode="nearest")
        return _stats_pool(x, weights.squeeze(1))

    def get_out_dim(self) -> int:
        return self.in_dim * 2


def get_nonlinear(config_str: str, channels: int) -> nn.Sequential:
    nonlinear = nn.Sequential()
    for name in config_str.split("-"):
        if name == "relu":
            nonlinear.add_module("relu", nn.ReLU(inplace=True))
        elif name == "prelu":
            nonlinear.add_module("prelu", nn.PReLU(channels))
        elif name == "batchnorm":
            nonlinear.add_module("batchnorm", nn.BatchNorm1d(channels))
        elif name == "batchnorm_":
            nonlinear.add_module("batchnorm", nn.BatchNorm1d(channels, affine=False))
        else:
            raise ValueError(f"Unexpected module ({name}).")
    return nonlinear


class TDNNLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int = 1,
        padding: int = 0,
        dilation: int = 1,
        bias: bool = False,
        config_str: str = "batchnorm-relu",
    ) -> None:
        super().__init__()
        if padding < 0:
            assert kernel_size % 2 == 1, (
                f"Expect equal paddings, but got even kernel size ({kernel_size})"
            )
            padding = (kernel_size - 1) // 2 * dilation
        self.linear = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
            bias=bias,
        )
        self.nonlinear = get_nonlinear(config_str, out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.nonlinear(self.linear(x))
        return out


class CAMLayer(nn.Module):
    def __init__(
        self,
        bn_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int,
        padding: int,
        dilation: int,
        bias: bool,
        reduction: int = 2,
    ) -> None:
        super().__init__()
        self.linear_local = nn.Conv1d(
            bn_channels,
            out_channels,
            kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
            bias=bias,
        )
        self.linear1 = nn.Conv1d(bn_channels, bn_channels // reduction, 1)
        self.relu = nn.ReLU(inplace=True)
        self.linear2 = nn.Conv1d(bn_channels // reduction, out_channels, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y: torch.Tensor = self.linear_local(x)
        # グローバル平均（全体コンテキスト）とセグメント平均（局所コンテキスト）を足してマスク計算
        context = x.mean(-1, keepdim=True) + self.seg_pooling(x)
        context = self.relu(self.linear1(context))
        m: torch.Tensor = self.sigmoid(self.linear2(context))
        return y * m

    def seg_pooling(self, x: torch.Tensor, seg_len: int = 100, stype: str = "avg") -> torch.Tensor:
        if stype == "avg":
            seg = F.avg_pool1d(x, kernel_size=seg_len, stride=seg_len, ceil_mode=True)
        elif stype == "max":
            seg = F.max_pool1d(x, kernel_size=seg_len, stride=seg_len, ceil_mode=True)
        else:
            raise ValueError("Wrong segment pooling type.")
        shape = seg.shape
        # 各セグメントの値を seg_len フレーム分に繰り返して元の時間長に戻す（最近傍アップサンプル）
        seg = (
            seg.unsqueeze(-1)
            .expand(shape[0], shape[1], shape[2], seg_len)
            .reshape(shape[0], shape[1], -1)
        )
        out: torch.Tensor = seg[..., : x.shape[-1]]
        return out


class CAMDenseTDNNLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        bn_channels: int,
        kernel_size: int,
        stride: int = 1,
        dilation: int = 1,
        bias: bool = False,
        config_str: str = "batchnorm-relu",
    ) -> None:
        super().__init__()
        assert kernel_size % 2 == 1, (
            f"Expect equal paddings, but got even kernel size ({kernel_size})"
        )
        padding = (kernel_size - 1) // 2 * dilation
        self.nonlinear1 = get_nonlinear(config_str, in_channels)
        self.linear1 = nn.Conv1d(in_channels, bn_channels, 1, bias=False)
        self.nonlinear2 = get_nonlinear(config_str, bn_channels)
        self.cam_layer = CAMLayer(
            bn_channels,
            out_channels,
            kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
            bias=bias,
        )

    def bn_function(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.linear1(self.nonlinear1(x))
        return out

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.bn_function(x)
        out: torch.Tensor = self.cam_layer(self.nonlinear2(x))
        return out


class CAMDenseTDNNBlock(nn.ModuleList):
    def __init__(
        self,
        num_layers: int,
        in_channels: int,
        out_channels: int,
        bn_channels: int,
        kernel_size: int,
        stride: int = 1,
        dilation: int = 1,
        bias: bool = False,
        config_str: str = "batchnorm-relu",
    ) -> None:
        super().__init__()
        for i in range(num_layers):
            layer = CAMDenseTDNNLayer(
                in_channels=in_channels + i * out_channels,
                out_channels=out_channels,
                bn_channels=bn_channels,
                kernel_size=kernel_size,
                stride=stride,
                dilation=dilation,
                bias=bias,
                config_str=config_str,
            )
            self.add_module(f"tdnnd{i + 1}", layer)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for layer in self:
            x = torch.cat(
                [x, layer(x)], dim=1
            )  # dense connection: 各層の出力を入力に追記していくのでチャンネルが増え続ける
        return x


class TransitLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        bias: bool = True,
        config_str: str = "batchnorm-relu",
    ) -> None:
        super().__init__()
        self.nonlinear = get_nonlinear(config_str, in_channels)
        self.linear = nn.Conv1d(in_channels, out_channels, 1, bias=bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.linear(self.nonlinear(x))
        return out


class DenseLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        bias: bool = False,
        config_str: str = "batchnorm-relu",
    ) -> None:
        super().__init__()
        self.linear = nn.Conv1d(in_channels, out_channels, 1, bias=bias)
        self.nonlinear = get_nonlinear(config_str, out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 2:
            x = self.linear(x.unsqueeze(dim=-1)).squeeze(dim=-1)
        else:
            x = self.linear(x)
        out: torch.Tensor = self.nonlinear(x)
        return out


class BasicResBlock(nn.Module):
    expansion = 1

    def __init__(self, in_planes: int, planes: int, stride: int = 1) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(
            in_planes, planes, kernel_size=3, stride=(stride, 1), padding=1, bias=False
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
                    stride=(stride, 1),
                    bias=False,
                ),
                nn.BatchNorm2d(self.expansion * planes),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = out + self.shortcut(x)
        return F.relu(out)


class FCM(nn.Module):
    def __init__(
        self,
        block: type[BasicResBlock],
        num_blocks: list[int],
        m_channels: int = 32,
        feat_dim: int = 80,
    ) -> None:
        super().__init__()
        self.in_planes = m_channels
        self.conv1 = nn.Conv2d(1, m_channels, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(m_channels)
        self.layer1 = self._make_layer(block, m_channels, num_blocks[0], stride=2)
        self.layer2 = self._make_layer(block, m_channels, num_blocks[1], stride=2)
        self.conv2 = nn.Conv2d(
            m_channels, m_channels, kernel_size=3, stride=(2, 1), padding=1, bias=False
        )
        self.bn2 = nn.BatchNorm2d(m_channels)
        self.out_channels = m_channels * (feat_dim // 8)

    def _make_layer(
        self,
        block: type[BasicResBlock],
        planes: int,
        num_blocks: int,
        stride: int,
    ) -> nn.Sequential:
        strides = [stride] + [1] * (num_blocks - 1)
        layers: list[nn.Module] = []
        for s in strides:
            layers.append(block(self.in_planes, planes, s))
            self.in_planes = planes * block.expansion
        return nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.unsqueeze(1)  # (B, F, T) → (B, 1, F, T): Conv2d はチャンネル次元が必要
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.layer1(out)  # stride=2 で周波数軸を半分に
        out = self.layer2(out)  # さらに半分
        out = F.relu(
            self.bn2(self.conv2(out))
        )  # stride=(2,1) で周波数軸をもう半分（時間軸はそのまま）
        shape = out.shape
        return out.reshape(
            shape[0], shape[1] * shape[2], shape[3]
        )  # (B, ch, F', T) → (B, ch*F', T): 以降は 1D Conv


class CAMPPlus(nn.Module):
    """CAM++ body. Input (B, T, F=80) → embedding (B, embed_dim=512).

    State-dict layout matches `Wespeaker/wespeaker-voxceleb-campplus/avg_model.pt`:
      `head.*`, `xvector.tdnn.*`, `xvector.block{1..3}.tdnnd{i}.*`,
      `xvector.transit{1..3}.*`, `xvector.out_nonlinear.*`, `xvector.dense.*`.
    """

    def __init__(
        self,
        feat_dim: int = 80,
        embed_dim: int = 512,
        growth_rate: int = 32,
        bn_size: int = 4,
        init_channels: int = 128,
        config_str: str = "batchnorm-relu",
    ) -> None:
        super().__init__()
        self.embed_dim = embed_dim
        self.head = FCM(block=BasicResBlock, num_blocks=[2, 2], feat_dim=feat_dim)
        channels = self.head.out_channels

        self.xvector = nn.Sequential(
            OrderedDict(
                [
                    (
                        "tdnn",
                        TDNNLayer(
                            channels,
                            init_channels,
                            5,
                            stride=2,
                            dilation=1,
                            padding=-1,
                            config_str=config_str,
                        ),
                    ),
                ]
            )
        )
        channels = init_channels
        for i, (num_layers, kernel_size, dilation) in enumerate(
            zip((12, 24, 16), (3, 3, 3), (1, 2, 2), strict=True)
        ):
            block = CAMDenseTDNNBlock(
                num_layers=num_layers,
                in_channels=channels,
                out_channels=growth_rate,
                bn_channels=bn_size * growth_rate,
                kernel_size=kernel_size,
                dilation=dilation,
                config_str=config_str,
            )
            self.xvector.add_module(f"block{i + 1}", block)
            channels = channels + num_layers * growth_rate
            self.xvector.add_module(
                f"transit{i + 1}",
                TransitLayer(channels, channels // 2, bias=False, config_str=config_str),
            )
            channels //= 2

        self.xvector.add_module("out_nonlinear", get_nonlinear(config_str, channels))

        self.pool = TSTP(in_dim=channels)
        self.pool_out_dim = self.pool.get_out_dim()
        # NOTE: pool is registered both as `self.pool` and `self.xvector.stats`
        # to match the upstream state_dict layout. TSTP has no learnable params,
        # so duplication is harmless.
        self.xvector.add_module("stats", self.pool)
        self.xvector.add_module(
            "dense", DenseLayer(self.pool_out_dim, embed_dim, config_str="batchnorm_")
        )

    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        """fbank (B, T, F) → frame-level features (B, C, T) just before pooling.

        Speaker-agnostic — does NOT take weights. Used by per-chunk strategy to
        share the heavy encoder forward across all local speakers of a chunk.
        """
        x = x.permute(0, 2, 1)  # (B, T, F) → (B, F, T)
        x = self.head(x)
        for name, module in self.xvector.named_children():
            if name == "stats":
                break  # stop before pooling — pooling needs per-speaker mask
            x = module(x)
        return x

    def forward_pool(
        self, features: torch.Tensor, weights: torch.Tensor | None = None
    ) -> torch.Tensor:
        """features (B, C, T), weights (B, T_w) → embedding (B, embed_dim)."""
        pooled: torch.Tensor = self.pool(features, weights=weights)
        dense = cast(DenseLayer, self.xvector.dense)
        out: torch.Tensor = dense(pooled)
        return out

    def forward(self, x: torch.Tensor, weights: torch.Tensor | None = None) -> torch.Tensor:
        """x: (B, T, F) → (B, embed_dim). `weights` (B, T_w) applied at pooling."""
        features = self.forward_features(x)
        return self.forward_pool(features, weights=weights)


class WeSpeakerCAMPlus(nn.Module):
    """End-to-end speaker embedding model: waveform → fbank → CAM++ → 512-dim.

    Drop-in replacement for `WeSpeakerResNet34`: identical `forward(waveforms,
    weights)` signature and same dimension / metric / min_num_samples props.
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
        embed_dim: int = 512,
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

        self.campplus = CAMPPlus(feat_dim=num_mel_bins, embed_dim=embed_dim)

    @property
    def dimension(self) -> int:
        return self.campplus.embed_dim

    @property
    def metric(self) -> str:
        return "cosine"

    @property
    def min_num_samples(self) -> int:
        return 8000

    def compute_fbank(self, waveforms: torch.Tensor) -> torch.Tensor:
        """waveforms: (B, 1, samples) → fbank (B, T, num_mel_bins).

        Matches WeSpeakerResNet34: int16-domain scaling, MPS FFT routed to CPU,
        per-utterance mean normalization.
        """
        waveforms = waveforms * (
            1 << 15
        )  # kaldi.fbank は int16 スケール（±32768）を前提としているので合わせる
        device = waveforms.device
        fft_device = (
            torch.device("cpu") if device.type == "mps" else device
        )  # kaldi の FFT が MPS 非対応なので CPU で計算
        features: torch.Tensor = torch.vmap(self._fbank)(waveforms.to(fft_device)).to(
            device
        )  # バッチを vmap で一括処理してデバイスに戻す
        return features - torch.mean(
            features, dim=1, keepdim=True
        )  # 発話単位の平均を引く（CMVN 的な正規化）

    def forward_features(self, waveforms: torch.Tensor) -> torch.Tensor:
        """waveforms (B, 1, samples) → frame-level features (B, C, T) before pooling.

        Speaker-agnostic encoder forward. Pair with `forward_pool()` to amortize
        encoder cost across multiple per-speaker masks of the same chunk
        (per-chunk strategy).
        """
        fbank = self.compute_fbank(waveforms)
        return self.campplus.forward_features(fbank)

    def forward_pool(
        self, features: torch.Tensor, weights: torch.Tensor | None = None
    ) -> torch.Tensor:
        """features (B, C, T), weights (B, T) → embedding (B, 512)."""
        return self.campplus.forward_pool(features, weights=weights)

    def forward(self, waveforms: torch.Tensor, weights: torch.Tensor | None = None) -> torch.Tensor:
        """waveforms: (B, 1, samples), weights: (B, T) optional → embedding (B, 512)."""
        fbank = self.compute_fbank(waveforms)
        emb: torch.Tensor = self.campplus(fbank, weights=weights)
        return emb

    @classmethod
    def from_wespeaker(
        cls,
        repo_id: str = "Wespeaker/wespeaker-voxceleb-campplus",
        filename: str = "avg_model.pt",
        token: str | None = None,
        cache_dir: str | None = None,
    ) -> WeSpeakerCAMPlus:
        """Load pretrained CAM++ weights from HuggingFace (cached locally)."""
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(repo_id=repo_id, filename=filename, token=token, cache_dir=cache_dir)
        state_dict: Any = torch.load(Path(path), map_location="cpu", weights_only=True)
        if not isinstance(state_dict, dict):
            raise RuntimeError(f"unexpected checkpoint format: {type(state_dict)}")

        instance = cls()
        own_keys = set(instance.campplus.state_dict().keys())
        filtered = {k: v for k, v in state_dict.items() if k in own_keys}
        missing, unexpected = instance.campplus.load_state_dict(filtered, strict=False)
        if missing or unexpected:
            raise RuntimeError(
                f"state_dict mismatch — missing={missing!r}, unexpected={unexpected!r}"
            )
        instance.eval()
        return instance
