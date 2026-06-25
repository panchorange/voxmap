"""ConformerEncoder (vendored, Phase 1) の軽量 smoke test。

NeMo / モデル DL は不要。ランダム重みで forward が通り、shape / length が
subsampling 規約どおり (時間 /8、channel-first 出力) になることだけ確認する。
数値一致 (vs NeMo) は tests/integration/test_conformer_parity.py 側。
"""

from __future__ import annotations

import torch

from voxmap.models.conformer import ConformerEncoder, calc_length


def _tiny_encoder() -> ConformerEncoder:
    # 本番より小さい構成で速く回す (属性名・forward 経路は同一)
    return ConformerEncoder(
        feat_in=128,
        n_layers=2,
        d_model=64,
        n_heads=4,
        ff_expansion_factor=2,
        conv_kernel_size=9,
        subsampling_factor=8,
        subsampling_conv_channels=16,
    )


def test_forward_shape_and_downsampling() -> None:
    enc = _tiny_encoder().eval()
    b, feat_in, t = 2, 128, 400
    x = torch.randn(b, feat_in, t)
    length = torch.tensor([t, t], dtype=torch.int64)

    with torch.no_grad():
        encoded, out_len = enc(x, length)

    expected_t = int(
        calc_length(torch.tensor(float(t)), all_paddings=2, kernel_size=3, stride=2, repeat_num=3)
    )
    assert encoded.shape == (b, 64, expected_t)  # channel-first
    assert out_len.tolist() == [expected_t, expected_t]


def test_padding_mask_changes_output() -> None:
    """短い length を渡すと padding がマスクされ、フル length と出力が変わる。"""
    enc = _tiny_encoder().eval()
    t = 400
    x = torch.randn(1, 128, t)
    with torch.no_grad():
        full, _ = enc(x, torch.tensor([t], dtype=torch.int64))
        half, half_len = enc(x, torch.tensor([t // 2], dtype=torch.int64))
    # 出力 length は短くなり、有効フレームの値も変わる
    assert int(half_len[0]) < int(_full_len(t))
    assert not torch.allclose(full[:, :, : int(half_len[0])], half[:, :, : int(half_len[0])])


def _full_len(t: int) -> torch.Tensor:
    return calc_length(
        torch.tensor(float(t)), all_paddings=2, kernel_size=3, stride=2, repeat_num=3
    )
