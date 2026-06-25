from voxmap.clustering.base import Clustering
from voxmap.embedding.base import Embedder
from voxmap.types import Audio, Diarization, SpeakerTurn
from voxmap.vad.base import VAD


class DefaultPipeline:
    def __init__(self, vad: VAD, embedder: Embedder, clustering: Clustering) -> None:
        self.vad = vad
        self.embedder = embedder
        self.clustering = clustering

    def __call__(self, audio: Audio, n_speakers: int | None = None) -> Diarization:
        segments = self.vad(audio)
        if not segments:
            return Diarization(turns=[])

        embeddings = self.embedder(audio, segments)
        labels = self.clustering(embeddings, n_speakers=n_speakers)

        turns = [
            SpeakerTurn(segment=seg, speaker=f"speaker_{int(label):02d}")
            for seg, label in zip(segments, labels, strict=True)
        ]
        return Diarization(turns=turns)
