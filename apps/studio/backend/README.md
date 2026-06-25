# voxmap-studio backend

フロントの「自動分離」を本物にする FastAPI サーバー。voxmap で話者分離する。
設計: `docs/design/annotation-tool/backend-design.md`。

依存方向は **backend → voxmap の一方向**。fastapi/uvicorn は voxmap に混ぜず、
ここ (uv workspace の別パッケージ) に閉じる。

## セットアップ・起動

ルートで uv workspace を sync してから起動する。

```sh
uv sync                       # workspace 全体 (voxmap + backend deps)
make studio-be-dev            # uvicorn 起動 (http://localhost:8000)
```

フロントは dev サーバー (`make studio-fe-dev`, :5173) が `/api` を :8000 にプロキシする。

## API

- `GET  /api/health` → `{ "status": "ok", "device": "mps|cuda|cpu" }`
- `POST /api/diarize` (multipart: `file`, 任意 `n_speakers`)
  → `{ "segments": [{ "start", "end", "speaker" }], "fileId" }`

## config

`app/config.yaml` = pyannote31-pe reference config (f=0.01 相対mcs / stride3 / centroid)。
`device: auto` は cuda > mps > cpu。

## 設計メモ

- モデルは起動時に1回ロードして再利用 (FastAPI lifespan)。
- 推論は `asyncio.Lock` で直列化 (話者分離だけなので並列不要、ローカル単一ユーザー前提)。
- fp16 / melspec fbank の RTF 最適化は未適用 (experiment の monkeypatch であり library 未対応)。
  follow-up で voxmap 側に昇格してから対応する。

## チェック

```sh
make studio-be-check          # ruff + mypy (strict)
make studio-be-test           # pytest (軽量スモーク)
```
