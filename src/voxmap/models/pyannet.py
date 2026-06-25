"""PyanNet — chunk-based speaker segmentation (powerset multilabel).

Vendored from pyannote.audio==4.0.4
  upstream: pyannote/audio/models/segmentation/PyanNet.py
  license:  MIT (see LICENSE.pyannote next to this file)
  reason:   Phase 2-1 vendor (see docs/design/decisions/2026-05-10_vendor_pyannote_models.md)

State-dict compatibility: layer names and shapes match upstream so weights from
`pyannote/segmentation-3.0` load via the `from_pyannote()` classmethod.

Architecture (powerset, max_classes=2, 3 local speakers):
  waveform (B, 1, 160000) →
    SincNet → (B, 60, 589) →
    BiLSTM ×2 → (B, 589, 256) →
    Linear ×2 → (B, 589, 128) →
    Linear → (B, 589, 7)  ← powerset logits
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from einops import rearrange
from pyannote.core.utils.generators import pairwise

from voxmap.models.blocks.sincnet import SincNet


class PyanNet(nn.Module):
    """SincNet → BiLSTM → Feed-forward → Classifier.

    Parameters
    ----------
    sincnet : dict, optional
        Overrides for SincNet. Defaults to {"stride": 10}.
    lstm : dict, optional
        Overrides for BiLSTM block.
    linear : dict, optional
        Overrides for linear stack.
    sample_rate : int, optional
        Always 16000 for the released checkpoints.
    num_classes : int, optional
        Output dimension. For powerset 3-speaker / max-2-active = 7.
    """

    SINCNET_DEFAULTS = {"stride": 10}
    LSTM_DEFAULTS = {
        "hidden_size": 128,
        "num_layers": 2,
        "bidirectional": True,
        "monolithic": True,
        "dropout": 0.0,
    }
    LINEAR_DEFAULTS = {"hidden_size": 128, "num_layers": 2}

    def __init__(
        self,
        sincnet: dict[str, Any] | None = None,
        lstm: dict[str, Any] | None = None,
        linear: dict[str, Any] | None = None,
        sample_rate: int = 16000,
        num_classes: int = 7,
    ) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self.num_classes = num_classes

        sincnet_cfg = {**self.SINCNET_DEFAULTS, **(sincnet or {})}
        sincnet_cfg["sample_rate"] = sample_rate
        lstm_cfg = {**self.LSTM_DEFAULTS, **(lstm or {})}
        lstm_cfg["batch_first"] = True
        linear_cfg = {**self.LINEAR_DEFAULTS, **(linear or {})}

        self._sincnet_cfg = sincnet_cfg
        self._lstm_cfg = lstm_cfg
        self._linear_cfg = linear_cfg

        self.sincnet = SincNet(**sincnet_cfg)

        # only the monolithic LSTM path is needed for the released 3.0 checkpoint
        lstm_kw = {k: v for k, v in lstm_cfg.items() if k != "monolithic"}
        if not lstm_cfg["monolithic"]:
            raise NotImplementedError(
                "non-monolithic LSTM is not vendored — "
                "released pyannote/segmentation-3.0 uses monolithic=True"
            )
        self.lstm = nn.LSTM(60, **lstm_kw)

        lstm_out = lstm_cfg["hidden_size"] * (2 if lstm_cfg["bidirectional"] else 1)
        if linear_cfg["num_layers"] > 0:
            self.linear = nn.ModuleList(
                [
                    nn.Linear(in_features, out_features)
                    for in_features, out_features in pairwise(
                        [lstm_out] + [linear_cfg["hidden_size"]] * linear_cfg["num_layers"]
                    )
                ]
            )
            classifier_in = linear_cfg["hidden_size"]
        else:
            self.linear = nn.ModuleList()
            classifier_in = lstm_out

        self.classifier = nn.Linear(classifier_in, num_classes)
        self.activation = nn.LogSoftmax(dim=-1)  # powerset uses log-softmax

    def num_frames(self, num_samples: int) -> int:
        return self.sincnet.num_frames(num_samples)

    def receptive_field_size(self, num_frames: int = 1) -> int:
        return self.sincnet.receptive_field_size(num_frames=num_frames)

    def receptive_field_center(self, frame: int = 0) -> int:
        return self.sincnet.receptive_field_center(frame=frame)

    def forward(self, waveforms: torch.Tensor) -> torch.Tensor:
        """waveforms: (batch, channel, sample) → log-probs (batch, frame, classes)."""
        outputs = self.sincnet(waveforms)
        outputs, _ = self.lstm(rearrange(outputs, "batch feature frame -> batch frame feature"))
        for linear in self.linear:
            outputs = F.leaky_relu(linear(outputs))
        result: torch.Tensor = self.activation(self.classifier(outputs))
        return result

    @classmethod
    def from_pyannote(
        cls,
        model_id: str = "pyannote/segmentation-3.0",
        token: str | None = None,
        cache_dir: str | None = None,
    ) -> PyanNet:
        """Bootstrap weights from pyannote checkpoint.

        Loads the original via `pyannote.audio.Model.from_pretrained`, copies
        hyperparameters + state_dict into our class. Eventual goal is to read
        the checkpoint directly (no pyannote import here) — see ADR.
        """
        from pyannote.audio import Model

        original = Model.from_pretrained(model_id, token=token, cache_dir=cache_dir, strict=False)
        if original is None:
            raise RuntimeError(f"pyannote.Model.from_pretrained({model_id!r}) returned None")

        spec: Any = original.specifications
        hp: Any = original.hparams
        # powerset: classes = C(K,0)+...+C(K,M); for K=3,M=2 → 7
        num_classes = spec.num_powerset_classes if spec.powerset else len(spec.classes)

        instance = cls(
            sincnet=dict(hp.sincnet),
            lstm=dict(hp.lstm),
            linear=dict(hp.linear),
            sample_rate=hp.sample_rate,
            num_classes=num_classes,
        )
        instance.load_state_dict(original.state_dict(), strict=True)
        instance.eval()

        # carry over the metadata adapters need (powerset flag, duration, classes)
        instance._specifications = spec
        return instance

    @property
    def specifications(self) -> Any:
        return getattr(self, "_specifications", None)
