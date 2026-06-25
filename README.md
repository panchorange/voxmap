# voxmap

A speaker diarization library and **voxmap-studio** — an open-source diarization
annotation tool that records annotation *cost* (typed edit-operation counts and
time) as a first-class output.

This repository accompanies the paper
*"voxmap-studio: an open-source speaker diarization annotation tool with
built-in cost instrumentation."* If you arrived here from the paper, the
annotation tool lives in [`apps/studio/`](apps/studio/).

## What is in this repository

```
voxmap/
├── apps/studio/        # voxmap-studio: the annotation tool (React frontend + FastAPI backend)
├── src/voxmap/         # the diarization library that powers automatic initialization
│   ├── vad/            #   voice activity detection
│   ├── embedding/      #   speaker embeddings
│   ├── clustering/     #   clustering
│   ├── pipeline/       #   VAD → embedding → clustering composed into a pipeline
│   └── eval/           #   DER / speaker-recall / latency / visualization
├── configs/            # reference pipeline configs (YAML)
├── scripts/            # CLIs: diarize / evaluate / compare_runs
└── tests/
```

## voxmap-studio

A browser-based tool for producing and correcting speaker diarization
annotations. Instead of drawing every speaker turn by hand, the annotator starts
from the output of a fast automatic diarization pipeline and *corrects* it.
Distinguishing features:

- **Automatic initialization.** The canvas is pre-filled by a stride-accelerated
  diarization engine, so the first annotation appears with little waiting.
- **Built-in cost instrumentation.** Every edit is counted by type
  (create / delete / split / resize / reassign) and active editing time is
  recorded, written into a JSON sidecar alongside the annotation — so you can
  measure *where* annotation effort actually goes.
- **Label assistance.** Segments likely to be mislabeled are highlighted, and a
  cluster gallery plus an `R`-key recommendation panel speed up labeling.
- **Confirmation-gated export.** The final RTTM/JSON is emitted only after every
  segment has been human-confirmed, with injected "phantom" attention checks
  that prevent unverified automatic output from being released as ground truth.

**→ Setup and how to run it:** [`apps/studio/README.md`](apps/studio/README.md)

**→ Keyboard shortcuts and the annotation workflow:**
[`apps/studio/USAGE.md`](apps/studio/USAGE.md)

## Using the library directly

The same engine that initializes the studio canvas can be used on its own.

```python
from voxmap.pipeline import build_pipeline

pipeline = build_pipeline("configs/pipeline/baseline.yaml")
diarization = pipeline.run("path/to/audio.wav")
```

```bash
# Run diarization and write RTTM
uv run python scripts/diarize.py audio.wav \
    --config configs/pipeline/baseline.yaml -o out.rttm

# Evaluate against a reference (DER + speaker recall)
uv run python scripts/evaluate.py --pred out.rttm --ref reference.rttm --out results/
```

Components are swappable: each `*/base.py` defines a `Protocol`, and any class
that satisfies it can be registered in `registry.py` and selected by name in a
config.

```yaml
vad:        { name: silero,    threshold: 0.5 }
embedding:  { name: wespeaker, model: voxceleb_resnet34 }
clustering: { name: spectral,  n_clusters: null }
```

## Development

```bash
make setup       # install dependencies (uv) and pre-commit hooks
make check       # ruff lint + mypy (strict)
make test        # pytest
```

Stack: Python 3.12 / [uv](https://github.com/astral-sh/uv) /
[ruff](https://github.com/astral-sh/ruff) / [mypy](https://mypy-lang.org/) (strict).
The studio frontend uses Bun + Vite + Biome; see
[`apps/studio/README.md`](apps/studio/README.md).

## License

See [LICENSE](LICENSE).
