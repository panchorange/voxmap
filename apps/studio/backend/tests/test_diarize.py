"""turns→dict 変換と health のスモークテスト。

実際の分離 (重いモデルロード) は CI 対象外。ここでは voxmap import なしで通る
軽量な単位のみ。"""

from __future__ import annotations

import torch

from app.diarize import resolve_device


def test_resolve_device_explicit() -> None:
    assert resolve_device("cpu") == torch.device("cpu")


def test_resolve_device_auto_returns_valid() -> None:
    dev = resolve_device("auto")
    assert dev.type in {"cuda", "mps", "cpu"}
