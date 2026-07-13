"""voxmap-studio backend (FastAPI)。

- モデルは起動時に1回ロードして再利用 (lifespan)。
- 推論は asyncio.Lock で直列化 (モデルは再入安全とは限らず、ローカル単一ユーザー前提)。
- ブロッキングな推論は to_thread でイベントループを塞がない。
"""

from __future__ import annotations

import asyncio
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import torch
import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from voxmap.pipeline.diarization31 import Diarization31Pipeline

from .diarize import DiarizeGrid, build_pipeline, diarize_file, recompute_signals, resolve_device
from .recommend import gallery_names, propose_cluster_mapping

CONFIG_PATH = Path(__file__).parent / "config.yaml"
GALLERY_ROOT = Path(__file__).parent.parent / "gallery"


class AppState:
    pipeline: Diarization31Pipeline | None = None
    device: torch.device | None = None
    config: dict[str, Any] = {}
    lock = asyncio.Lock()
    # 直近の分離が出した埋め込みグリッド (編集追従の再計算用)。1 セッション 1 件。
    grid: DiarizeGrid | None = None


state = AppState()


class RecomputeSegment(BaseModel):
    start: float
    end: float
    speaker: str


class RecomputeRequest(BaseModel):
    segments: list[RecomputeSegment]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    with CONFIG_PATH.open() as f:
        config = yaml.safe_load(f)
    state.config = config
    state.device = resolve_device(str(config["pipeline"].get("device", "auto")))
    state.pipeline = build_pipeline(config, state.device)
    yield


app = FastAPI(title="voxmap-studio", lifespan=lifespan)

# dev は Vite proxy (/api -> :8000) 経由なので CORS は本来不要だが、直アクセス用に許可。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "device": str(state.device)}


@app.get("/api/gallery/preview")
async def gallery_preview(name: str) -> FileResponse:
    """既知話者の代表クリップ (build_gallery が保存した wav) を返す。試聴用。

    `name` は `EN2002a/MEE073` のような相対パス。`GALLERY_ROOT` 外への
    パストラバーサルを弾く。クリップが無ければ 404 (古い gallery など)。
    """
    root = GALLERY_ROOT.resolve()
    # 新構造: gallery/<meeting>/audio/<speaker>.wav
    # 旧構造: gallery/<meeting>/<speaker>.wav (後方互換)
    target = (root / Path(name).parent / "audio" / f"{Path(name).name}.wav").resolve()
    if root not in target.parents or not target.is_file():
        target = (root / f"{name}.wav").resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="clip not found")
    return FileResponse(target, media_type="audio/wav")


@app.post("/api/diarize")
async def diarize(
    file: Annotated[UploadFile, File()],
    n_speakers: Annotated[int | None, Form()] = None,
    min_duration_on: Annotated[float | None, Form()] = None,
) -> dict[str, Any]:
    assert state.pipeline is not None  # lifespan でロード済み
    if (
        min_duration_on is not None
        and min_duration_on != 0.0
        and not (0.1 <= min_duration_on <= 1.0)
    ):
        raise HTTPException(
            status_code=400, detail="min_duration_on must be 0.0 (disabled) or in [0.1, 1.0]"
        )
    filename = file.filename or "audio"
    data = await file.read()

    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    delta = float(state.config.get("suspicion", {}).get("delta", 0.05))
    rec_threshold = float(state.config.get("recommend", {}).get("threshold", 0.3))
    try:
        async with state.lock:
            result = await asyncio.to_thread(
                diarize_file,
                state.pipeline,
                tmp_path,
                n_speakers,
                delta,
                rec_threshold,
                min_duration_on,
            )
    finally:
        tmp_path.unlink(missing_ok=True)

    # 編集追従の再計算用にグリッドを保持 (フロントには返さない)。
    state.grid = result["grid"]

    file_id = Path(filename).stem
    # クラスタ重心 → 全既知話者の対応表 (一括対応ポップアップ用)。会議スコープに縛らず
    # gallery 配下の全 npy を候補にする。重心は再利用なので追加コストは数 ms (再埋め込みなし)。
    cluster_mapping = propose_cluster_mapping(result["centroids"], GALLERY_ROOT, state.config)

    return {
        "segments": result["segments"],
        "suspicion": result["suspicion"],
        "recommendation": result["recommendation"],
        "fileId": file_id,
        "clusterMapping": cluster_mapping,
        "galleryNames": gallery_names(GALLERY_ROOT),
    }


@app.post("/api/recompute")
async def recompute(req: RecomputeRequest) -> dict[str, Any]:
    """編集後の segment 群に怪しさ/レコメンドを追従させる (再埋め込みなし)。

    直近の分離が出した埋め込みグリッドを再利用し、編集後の窓で emb_seg を引き直す。
    分離前/グリッド無しは 409。リネーム済み等の未知 speaker は null (フロントで保持)。
    """
    if state.grid is None:
        raise HTTPException(status_code=409, detail="no diarization grid; run /api/diarize first")
    delta = float(state.config.get("suspicion", {}).get("delta", 0.05))
    rec_threshold = float(state.config.get("recommend", {}).get("threshold", 0.3))
    segments = [{"start": s.start, "end": s.end, "speaker": s.speaker} for s in req.segments]
    async with state.lock:
        susp, rec = await asyncio.to_thread(
            recompute_signals, segments, state.grid, delta, rec_threshold
        )
    return {"suspicion": susp, "recommendation": rec}
