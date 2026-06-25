"""Conformer encoder (FastConformer, dw_striding subsampling) — ASR encoder.

Vendored from NVIDIA NeMo (NVIDIA-NeMo/NeMo)
  upstream:
    nemo/collections/asr/modules/conformer_encoder.py        (ConformerEncoder)
    nemo/collections/asr/parts/submodules/conformer_modules.py
        (ConformerLayer, ConformerConvolution, ConformerFeedForward)
    nemo/collections/asr/parts/submodules/multi_head_attention.py
        (RelPositionMultiHeadAttention, RelPositionalEncoding)
    nemo/collections/asr/parts/submodules/subsampling.py     (ConvSubsampling)
  pinned to: nemo-toolkit 2.1.0
  license:  Apache 2.0 (see LICENSE.nemo next to this file)

Scope (Phase 1, ADR 2026-05-28_vendor_parakeet_conformer):
  Inference-only re-implementation of the encoder used by
  `nvidia/parakeet-tdt-0.6b-v3`. Module attribute names mirror NeMo exactly so
  that `ConformerEncoder.load_state_dict(nemo_model.encoder.state_dict())` loads
  without remapping. Streaming / caching / adapters / stochastic-depth /
  reduction / sdpa branches are dropped (not used at inference for this model).

parakeet-tdt-0.6b-v3 encoder config:
  feat_in=128, d_model=1024, n_layers=24, n_heads=8, ff_expansion_factor=4
  (d_ff=4096), subsampling=dw_striding x8 (conv_channels=256), conv_kernel_size=9,
  conv_norm_type=batch_norm, self_attention_model=rel_pos, att_context=[-1,-1]
  (full, regular), xscaling=false, untie_biases=true, use_bias=false.

Architecture (16kHz mono, 128-mel):
  mel (B, 128, T) →
    ConvSubsampling (3x stride-2 conv2d, /8 in time) → (B, T', 1024)
    RelPositionalEncoding → pos_emb (1, 2T'-1, 1024)
    24 x ConformerLayer (FFN/2 → MHSA(rel_pos) → Conv → FFN/2, pre-norm) →
  (B, 1024, T')  ← encoded (channel-first, matches NeMo output)
"""

from __future__ import annotations

import math

import torch
from torch import nn

INF_VAL = 10000.0


def calc_length(
    length: torch.Tensor, all_paddings: int, kernel_size: int, stride: int, repeat_num: int
) -> torch.Tensor:
    """Output length after `repeat_num` conv layers (floor mode). Mirrors NeMo."""
    add_pad = float(all_paddings - kernel_size)
    for _ in range(repeat_num):
        length = torch.div(length.to(torch.float) + add_pad, stride) + 1.0
        length = torch.floor(length)
    return length.to(torch.int)


class ConvSubsampling(nn.Module):
    """dw_striding subsampling: 3x stride-2 conv2d, time downsampled by 8."""

    def __init__(self, feat_in: int, d_model: int, conv_channels: int = 256, factor: int = 8):
        super().__init__()
        self._sampling_num = int(math.log2(factor))
        self._stride = 2
        self._kernel_size = 3
        self._left_padding = (self._kernel_size - 1) // 2
        self._right_padding = (self._kernel_size - 1) // 2

        layers: list[nn.Module] = []
        in_ch = 1
        layers.append(
            nn.Conv2d(
                in_ch,
                conv_channels,
                self._kernel_size,
                stride=self._stride,
                padding=self._left_padding,
            )
        )
        layers.append(nn.ReLU(inplace=True))
        in_ch = conv_channels
        for _ in range(self._sampling_num - 1):
            layers.append(
                nn.Conv2d(
                    in_ch,
                    in_ch,
                    self._kernel_size,
                    stride=self._stride,
                    padding=self._left_padding,
                    groups=in_ch,
                )
            )
            layers.append(nn.Conv2d(in_ch, conv_channels, kernel_size=1, stride=1, padding=0))
            layers.append(nn.ReLU(inplace=True))
            in_ch = conv_channels
        self.conv = nn.Sequential(*layers)

        out_length = calc_length(
            torch.tensor(feat_in, dtype=torch.float),
            all_paddings=self._left_padding + self._right_padding,
            kernel_size=self._kernel_size,
            stride=self._stride,
            repeat_num=self._sampling_num,
        )
        self.out = nn.Linear(conv_channels * int(out_length), d_model)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        lengths = calc_length(
            lengths,
            all_paddings=self._left_padding + self._right_padding,
            kernel_size=self._kernel_size,
            stride=self._stride,
            repeat_num=self._sampling_num,
        )
        x = x.unsqueeze(1)  # (B, 1, T, feat_in)
        x = self.conv(x)
        b, c, t, f = x.size()
        x = self.out(x.transpose(1, 2).reshape(b, t, c * f))  # (B, T', d_model)
        return x, lengths


class RelPositionalEncoding(nn.Module):
    """Transformer-XL relative positional encoding. `pe` is a non-persistent buffer."""

    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        self.d_model = d_model
        self.max_len = max_len
        self.pe: torch.Tensor

    def extend_pe(self, length: int, device: torch.device, dtype: torch.dtype) -> None:
        needed = 2 * length - 1
        if hasattr(self, "pe") and self.pe is not None and self.pe.size(1) >= needed:
            return
        positions = torch.arange(
            length - 1, -length, -1, dtype=torch.float32, device=device
        ).unsqueeze(1)
        pe = torch.zeros(positions.size(0), self.d_model, device=device)
        div_term = torch.exp(
            torch.arange(0, self.d_model, 2, dtype=torch.float32, device=device)
            * -(math.log(INF_VAL) / self.d_model)
        )
        pe[:, 0::2] = torch.sin(positions * div_term)
        pe[:, 1::2] = torch.cos(positions * div_term)
        self.pe = pe.unsqueeze(0).to(dtype)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return pos_emb (1, 2T-1, d_model) centred on the current length."""
        input_len = x.size(1)
        center_pos = self.pe.size(1) // 2 + 1
        start_pos = center_pos - input_len
        end_pos = center_pos + input_len - 1
        return self.pe[:, start_pos:end_pos]


class RelPositionMultiHeadAttention(nn.Module):
    """Multi-head self-attention with Transformer-XL relative positional bias."""

    def __init__(self, n_head: int, n_feat: int, use_bias: bool = False):
        super().__init__()
        assert n_feat % n_head == 0
        self.d_k = n_feat // n_head
        self.s_d_k = math.sqrt(self.d_k)
        self.h = n_head
        self.linear_q = nn.Linear(n_feat, n_feat, bias=use_bias)
        self.linear_k = nn.Linear(n_feat, n_feat, bias=use_bias)
        self.linear_v = nn.Linear(n_feat, n_feat, bias=use_bias)
        self.linear_out = nn.Linear(n_feat, n_feat, bias=use_bias)
        self.linear_pos = nn.Linear(n_feat, n_feat, bias=False)
        self.pos_bias_u = nn.Parameter(torch.zeros(self.h, self.d_k))
        self.pos_bias_v = nn.Parameter(torch.zeros(self.h, self.d_k))

    def forward_qkv(
        self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        b = query.size(0)
        q = self.linear_q(query).view(b, -1, self.h, self.d_k).transpose(1, 2)
        k = self.linear_k(key).view(b, -1, self.h, self.d_k).transpose(1, 2)
        v = self.linear_v(value).view(b, -1, self.h, self.d_k).transpose(1, 2)
        return q, k, v

    def rel_shift(self, x: torch.Tensor) -> torch.Tensor:
        b, h, qlen, pos_len = x.size()
        x = nn.functional.pad(x, pad=(1, 0))
        x = x.view(b, h, -1, qlen)
        return x[:, :, 1:].view(b, h, qlen, pos_len)

    def forward(
        self, x: torch.Tensor, pos_emb: torch.Tensor, mask: torch.Tensor | None
    ) -> torch.Tensor:
        q, k, v = self.forward_qkv(x, x, x)
        q = q.transpose(1, 2)  # (B, T, h, d_k)

        n_batch_pos = pos_emb.size(0)
        p = self.linear_pos(pos_emb).view(n_batch_pos, -1, self.h, self.d_k).transpose(1, 2)

        q_with_bias_u = (q + self.pos_bias_u).transpose(1, 2)  # (B, h, T, d_k)
        q_with_bias_v = (q + self.pos_bias_v).transpose(1, 2)

        matrix_bd = torch.matmul(q_with_bias_v, p.transpose(-2, -1))
        matrix_bd = self.rel_shift(matrix_bd)

        matrix_ac = torch.matmul(q_with_bias_u, k.transpose(-2, -1))
        matrix_bd = matrix_bd[:, :, :, : matrix_ac.size(-1)]
        scores = (matrix_ac + matrix_bd) / self.s_d_k

        return self.forward_attention(v, scores, mask)

    def forward_attention(
        self, value: torch.Tensor, scores: torch.Tensor, mask: torch.Tensor | None
    ) -> torch.Tensor:
        b = value.size(0)
        if mask is not None:
            mask = mask.unsqueeze(1)
            scores = scores.masked_fill(mask, -INF_VAL)
            attn = torch.softmax(scores, dim=-1).masked_fill(mask, 0.0)
        else:
            attn = torch.softmax(scores, dim=-1)
        x = torch.matmul(attn, value)
        x = x.transpose(1, 2).reshape(b, -1, self.h * self.d_k)
        out: torch.Tensor = self.linear_out(x)
        return out


class ConformerFeedForward(nn.Module):
    def __init__(self, d_model: int, d_ff: int, use_bias: bool = False):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff, bias=use_bias)
        self.activation = nn.SiLU()  # Swish
        self.linear2 = nn.Linear(d_ff, d_model, bias=use_bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.linear2(self.activation(self.linear1(x)))
        return out


class ConformerConvolution(nn.Module):
    def __init__(self, d_model: int, kernel_size: int, use_bias: bool = False):
        super().__init__()
        assert (kernel_size - 1) % 2 == 0
        padding = (kernel_size - 1) // 2
        self.pointwise_conv1 = nn.Conv1d(d_model, d_model * 2, kernel_size=1, bias=use_bias)
        # CausalConv1D(cache=None) == Conv1d with symmetric padding; same param name.
        self.depthwise_conv = nn.Conv1d(
            d_model,
            d_model,
            kernel_size=kernel_size,
            padding=padding,
            groups=d_model,
            bias=use_bias,
        )
        self.batch_norm = nn.BatchNorm1d(d_model)
        self.activation = nn.SiLU()  # Swish
        self.pointwise_conv2 = nn.Conv1d(d_model, d_model, kernel_size=1, bias=use_bias)

    def forward(self, x: torch.Tensor, pad_mask: torch.Tensor | None) -> torch.Tensor:
        x = x.transpose(1, 2)  # (B, d, T)
        x = self.pointwise_conv1(x)
        x = nn.functional.glu(x, dim=1)
        if pad_mask is not None:
            x = x.masked_fill(pad_mask.unsqueeze(1), 0.0)
        x = self.depthwise_conv(x)
        x = self.batch_norm(x)
        x = self.activation(x)
        x = self.pointwise_conv2(x)
        return x.transpose(1, 2)


class ConformerLayer(nn.Module):
    def __init__(
        self, d_model: int, d_ff: int, n_heads: int, conv_kernel_size: int, use_bias: bool = False
    ):
        super().__init__()
        self.fc_factor = 0.5
        self.norm_feed_forward1 = nn.LayerNorm(d_model)
        self.feed_forward1 = ConformerFeedForward(d_model, d_ff, use_bias=use_bias)
        self.norm_conv = nn.LayerNorm(d_model)
        self.conv = ConformerConvolution(d_model, conv_kernel_size, use_bias=use_bias)
        self.norm_self_att = nn.LayerNorm(d_model)
        self.self_attn = RelPositionMultiHeadAttention(n_heads, d_model, use_bias=use_bias)
        self.norm_feed_forward2 = nn.LayerNorm(d_model)
        self.feed_forward2 = ConformerFeedForward(d_model, d_ff, use_bias=use_bias)
        self.norm_out = nn.LayerNorm(d_model)

    def forward(
        self,
        x: torch.Tensor,
        att_mask: torch.Tensor | None,
        pos_emb: torch.Tensor,
        pad_mask: torch.Tensor | None,
    ) -> torch.Tensor:
        residual = x
        x = self.feed_forward1(self.norm_feed_forward1(x))
        residual = residual + x * self.fc_factor

        x = self.norm_self_att(residual)
        x = self.self_attn(x, pos_emb=pos_emb, mask=att_mask)
        residual = residual + x

        x = self.norm_conv(residual)
        x = self.conv(x, pad_mask=pad_mask)
        residual = residual + x

        x = self.feed_forward2(self.norm_feed_forward2(residual))
        residual = residual + x * self.fc_factor

        out: torch.Tensor = self.norm_out(residual)
        return out


class ConformerEncoder(nn.Module):
    """FastConformer encoder for parakeet-tdt-0.6b-v3 (inference-only)."""

    def __init__(
        self,
        feat_in: int = 128,
        n_layers: int = 24,
        d_model: int = 1024,
        n_heads: int = 8,
        ff_expansion_factor: int = 4,
        conv_kernel_size: int = 9,
        subsampling_factor: int = 8,
        subsampling_conv_channels: int = 256,
        pos_emb_max_len: int = 5000,
        use_bias: bool = False,
    ):
        super().__init__()
        d_ff = d_model * ff_expansion_factor
        self.pre_encode = ConvSubsampling(
            feat_in, d_model, conv_channels=subsampling_conv_channels, factor=subsampling_factor
        )
        self.pos_enc = RelPositionalEncoding(d_model, max_len=pos_emb_max_len)
        self.layers = nn.ModuleList(
            ConformerLayer(d_model, d_ff, n_heads, conv_kernel_size, use_bias=use_bias)
            for _ in range(n_layers)
        )

    def forward(
        self, audio_signal: torch.Tensor, length: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """audio_signal: (B, feat_in, T). Returns (encoded (B, d_model, T'), out_length)."""
        if length is None:
            length = audio_signal.new_full(
                (audio_signal.size(0),), audio_signal.size(-1), dtype=torch.int64
            )

        audio_signal = audio_signal.transpose(1, 2)  # (B, T, feat_in)
        audio_signal, length = self.pre_encode(audio_signal, length)
        length = length.to(torch.int64)

        max_len = audio_signal.size(1)
        self.pos_enc.extend_pe(max_len, audio_signal.device, audio_signal.dtype)
        pos_emb = self.pos_enc(audio_signal)

        pad_mask, att_mask = self._create_masks(length, max_len, audio_signal.device)

        for layer in self.layers:
            audio_signal = layer(
                audio_signal, att_mask=att_mask, pos_emb=pos_emb, pad_mask=pad_mask
            )

        audio_signal = audio_signal.transpose(1, 2)  # (B, d_model, T')
        return audio_signal, length

    @staticmethod
    def _create_masks(
        length: torch.Tensor, max_len: int, device: torch.device
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # full attention (att_context=[-1,-1], regular) → only padding is masked
        valid = torch.arange(0, max_len, device=device).expand(
            length.size(0), -1
        ) < length.unsqueeze(-1)
        pad_for_att = valid.unsqueeze(1).repeat(1, max_len, 1)
        pad_for_att = torch.logical_and(pad_for_att, pad_for_att.transpose(1, 2))
        att_mask = ~pad_for_att  # True = ignore
        pad_mask = ~valid  # True = padding
        return pad_mask, att_mask
