import numpy as np
import torch
from numpy.typing import NDArray
from pyannote.audio import Inference, Model

from voxmap.types import Audio, Segment


class PyannoteEmbedder:
    def __init__(
        self,
        model_name: str = "pyannote/embedding",
        auth_token: str | None = None,
        min_duration: float = 0.5,
    ) -> None:
        model = Model.from_pretrained(model_name, token=auth_token)
        if model is None:
            raise RuntimeError(
                f"Failed to load pyannote model {model_name!r}. "
                "Check the model name and HuggingFace token."
            )
        self._inference = Inference(model, window="whole")
        self.min_duration = min_duration

    def __call__(self, audio: Audio, segments: list[Segment]) -> NDArray[np.float32]:
        if not segments:
            return np.empty((0, 0), dtype=np.float32)

        sr = audio.sample_rate
        n_samples = audio.waveform.shape[1]
        min_samples = int(self.min_duration * sr)

        embeddings = [
            self._embed(audio.waveform, seg, sr, n_samples, min_samples) for seg in segments
        ]
        return np.stack(embeddings).astype(np.float32)

    def _embed(
        self,
        waveform: torch.Tensor,
        seg: Segment,
        sr: int,
        n_samples: int,
        min_samples: int,
    ) -> NDArray[np.float32]:
        start = max(0, int(seg.start * sr))
        end = min(n_samples, int(seg.end * sr))
        if end - start < min_samples:
            deficit = min_samples - (end - start)
            start = max(0, start - deficit // 2)
            end = min(n_samples, start + min_samples)
            if end - start < min_samples:  # hit end of file
                start = max(0, end - min_samples)
        result = self._inference({"waveform": waveform[:, start:end], "sample_rate": sr})
        return np.asarray(result, dtype=np.float32)
