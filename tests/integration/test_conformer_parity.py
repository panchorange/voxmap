"""Phase 1 検証ゲート: 自前 ConformerEncoder が NeMo encoder と数値一致するか。

ADR 2026-05-28_vendor_parakeet_conformer の検証:
  同一入力に対し出力テンソルの cos 類似 > 0.999 を要求する。

NeMo + モデル DL (~600MB) が必要なので、既定ではスキップ。実行するには:
  VOXMAP_PARITY=1 uv run pytest tests/integration/test_conformer_parity.py -s
"""

from __future__ import annotations

import os

import pytest
import torch

pytestmark = pytest.mark.skipif(
    not os.getenv("VOXMAP_PARITY"),
    reason="NeMo + モデル DL が必要。VOXMAP_PARITY=1 で実行",
)

_MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v3"


def test_encoder_output_parity_vs_nemo() -> None:
    import nemo.collections.asr as nemo_asr

    from voxmap.models.conformer import ConformerEncoder

    model = nemo_asr.models.ASRModel.from_pretrained(model_name=_MODEL_NAME)
    model = model.to("cpu").float().eval()

    enc = ConformerEncoder(
        feat_in=model.cfg.encoder.feat_in,
        n_layers=model.cfg.encoder.n_layers,
        d_model=model.cfg.encoder.d_model,
        n_heads=model.cfg.encoder.n_heads,
        ff_expansion_factor=model.cfg.encoder.ff_expansion_factor,
        conv_kernel_size=model.cfg.encoder.conv_kernel_size,
        subsampling_factor=model.cfg.encoder.subsampling_factor,
        subsampling_conv_channels=model.cfg.encoder.subsampling_conv_channels,
        pos_emb_max_len=model.cfg.encoder.pos_emb_max_len,
        use_bias=model.cfg.encoder.use_bias,
    )
    enc.load_state_dict(model.encoder.state_dict())
    enc = enc.float().eval()

    torch.manual_seed(0)
    feat_in = model.cfg.encoder.feat_in
    t = 200
    mel = torch.randn(1, feat_in, t)
    length = torch.tensor([t], dtype=torch.int64)

    with torch.no_grad():
        ref, ref_len = model.encoder(audio_signal=mel, length=length)
        ours, ours_len = enc(mel, length)

    assert ours.shape == ref.shape
    assert ours_len.tolist() == ref_len.tolist()

    cos = torch.nn.functional.cosine_similarity(
        ours.flatten().unsqueeze(0), ref.flatten().unsqueeze(0)
    ).item()
    max_abs = (ours - ref).abs().max().item()
    print(f"\ncos={cos:.6f}  max_abs_diff={max_abs:.3e}")
    assert cos > 0.999, f"encoder output cos {cos} <= 0.999"
