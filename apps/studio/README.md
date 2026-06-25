# voxmap-studio

voxmap エンジンを使った GUI アプリ。話者分離アノテーション + 音声再生 + ASR を載せ、
研究者にも一般ユーザーにも使えることを目指す。

配置・依存方針は ADR (`docs/design/decisions/2026-06-02_app-layer-voxmap-studio.md`) を参照。
依存方向は **`apps/studio → voxmap` の一方向**。ASR は `src/voxmap/asr` /
`src/voxmap/asr_diarization` を呼び、アプリ独自実装は持たない。

## 構成

```
apps/studio/
├─ frontend/   # React + Vite (Bun で実行) / lint+format は Biome / 型は tsc strict
└─ backend/    # FastAPI (voxmap を import)
```

## 前提ツール (WSL / Linux / macOS)

> Windows をネイティブ (PowerShell) で動かす場合は下の
> [Windows (PowerShell) でのセットアップ](#windows-powershell-でのセットアップ) を参照。
> 以降の `make studio-*` ターゲットは bash + GNU make 前提。

make ターゲットは以下が PATH にある前提。未導入なら先に入れる (リポジトリ root の
`make studio-fe-*` を初めて叩く前に必要)。

- **Bun** — フロントの install/run。未導入だと `make studio-fe-setup` が
  `bun: not found` で落ちる。
  ```sh
  sudo apt install -y unzip                  # インストーラが unzip を要求 (WSL/Ubuntu に無いことが多い)
  curl -fsSL https://bun.sh/install | bash   # ~/.bun/bin にインストール
  exec $SHELL -l                             # PATH を反映 (or 新しいシェルを開く)
  bun --version                              # 確認
  ```
- **uv** — backend (FastAPI + voxmap) の実行。エンジン側と同じ。リポジトリ root の
  README / 開発ルール参照。

## フロント開発

ツールチェーン: **Bun** (install/run) + **Vite** (bundler/HMR) + **Biome** (lint+format) + **tsc --strict** (型)。
pre-commit は **lefthook** (Python 側の pre-commit とは分離)。

```sh
make studio-fe-setup   # bun install + lefthook install
make studio-fe-dev     # 開発サーバー (http://localhost:5173, /api を :8000 にプロキシ)
make studio-fe-check   # biome check + tsc --noEmit
make studio-fe-fix     # biome check --write
```

## バックエンド開発

FastAPI。起動時に voxmap pipeline を1回ロードして再利用する (`app/main.py`)。
依存は engine 側 (`uv`) を共有。

```sh
make studio-be-dev     # uvicorn 開発サーバー (http://localhost:8000, --reload)
make studio-be-check   # ruff check + mypy
make studio-be-test    # pytest
```

フロントの `/api` は dev サーバーが `:8000` にプロキシするので、フルに動かすには
`studio-be-dev` と `studio-fe-dev` を両方立てる。

## Windows (PowerShell) でのセットアップ

WSL を使わず、ネイティブ Windows + PowerShell で動かす手順。GPU は不要 (無ければ
CPU で起動する。`device: auto` が `cuda > mps > cpu` でフォールバック)。

> **`make` は使わない**。Windows ネイティブには GNU make が無いので、Makefile
> ターゲットの中身 (生コマンド) を直接叩く。以下がその対応。

### 1. ツールを入れる (初回のみ)

PowerShell で実行し、各インストール後は **PATH 反映のため一度ターミナルを開き直す**。

```powershell
# Bun (フロント install/run)
irm bun.sh/install.ps1 | iex

# uv (backend = FastAPI + voxmap の実行)
irm https://astral.sh/uv/install.ps1 | iex
```

確認:

```powershell
bun --version
uv --version
```

### 2. HuggingFace トークン (必須)

backend は起動時に gated model `pyannote/segmentation-3.0` をロードする。事前に
HF サイトでこのモデルのライセンスに同意し、アクセストークンを発行しておく。
PowerShell セッションに設定する (恒久化するなら `setx HF_TOKEN ...` で環境変数に)。

```powershell
$env:HF_TOKEN = "hf_xxxxxxxx"
```

> 未設定だと backend が起動時 (lifespan) のモデルロードで失敗する。初回はモデル
> 重み (segmentation + CAM++ embedding) のダウンロードが走るのでネットワーク必須。

### 3. バックエンドを起動

リポジトリ root で workspace を sync してから uvicorn を起動する。

```powershell
# リポジトリ root で
uv sync                       # voxmap + backend 依存を一括解決
$env:HF_TOKEN = "hf_xxxxxxxx" # (新しいシェルなら再設定)
cd apps\studio\backend
uv run uvicorn app.main:app --reload --port 8000
```

`http://localhost:8000/api/health` が `{"status":"ok","device":"cpu"}` を返せばOK。

### 4. フロントを起動 (別の PowerShell ウィンドウで)

```powershell
cd apps\studio\frontend
bun install
bun run dev                   # http://localhost:5173
```

ブラウザで `http://localhost:5173` を開く。フロントの `/api` は :8000 の backend に
プロキシされる (両方立っている必要がある)。

### make ターゲットとの対応

| make (WSL/Linux) | Windows PowerShell での生コマンド |
|---|---|
| `make studio-fe-setup` | `cd apps\studio\frontend; bun install` |
| `make studio-fe-dev` | `cd apps\studio\frontend; bun run dev` |
| `make studio-fe-check` | `cd apps\studio\frontend; bun run lint; bun run typecheck` |
| `make studio-be-dev` | `uv sync` (root) → `cd apps\studio\backend; uv run uvicorn app.main:app --reload --port 8000` |
| `make studio-be-check` | `cd apps\studio\backend; uv run ruff check app; uv run mypy app` |
| `make studio-be-test` | `cd apps\studio\backend; uv run pytest` |

> lefthook (フロントの pre-commit) は起動には不要。コミットフックも使うなら
> `cd apps\studio\frontend; bun add --dev lefthook; bunx lefthook install`。
