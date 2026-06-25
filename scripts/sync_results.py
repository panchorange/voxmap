"""Sync a subdir (default: results/) between local repo and GCS (gs://voxmap).

Usage:
    uv run python scripts/sync_results.py upload   <kind>/<theme>/<id> [--subdir results]
    uv run python scripts/sync_results.py download <kind>/<theme>/<id> [--subdir results]
    uv run python scripts/sync_results.py list     <kind>/<theme>/<id> [--subdir results]
    uv run python scripts/sync_results.py upload-all   [--kind experiments|profiles|analysis]
    uv run python scripts/sync_results.py download-all [--kind experiments|profiles|analysis]

  <kind>:  experiments / profiles / analysis
  <theme>: テーマディレクトリ (e.g., 2026-05-27_ASR-diarization)
  <id>:    計測/実験 ID (e.g., 2026-05-30_parakeet-mlx)
  → experiments / profiles / analysis すべて `<theme>/<id>` の2階層

  --subdir: GCS にミラーするサブフォルダ。default は `results`。
            results 以外 (例: annotation テーマの git 管理外 `sidecars/`) を上げたいときは
            別ランで `--subdir sidecars` のように指定する (results は無改修で従来どおり)。
            GCS パスは `gs://voxmap/<kind>/<theme>/<id>/<subdir>/` でローカルと 1:1。

gcloud CLI が必要 (`gcloud auth list` で認証済みを確認)。
失敗した場合は exit 1。upload-all / download-all は個別失敗をスキップして集計表示する。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

REPO_ROOT = Path(__file__).resolve().parents[1]
GCS_BUCKET = "gs://voxmap"
VALID_KINDS = ("experiments", "profiles", "analysis")

app = typer.Typer(add_completion=False)


def _split_target(target: str) -> tuple[str, str]:
    """`<kind>/<theme>/<id>` のような文字列を (kind, "<theme>/<id>") に分解。"""
    parts = target.split("/", 1)
    if len(parts) != 2 or parts[0] not in VALID_KINDS:
        raise typer.BadParameter(
            f"target は `<kind>/<theme>/<id>` 形式で kind ∈ {VALID_KINDS} (got {target!r})"
        )
    kind, id_ = parts
    if not id_:
        raise typer.BadParameter("id が空")
    return kind, id_


def _validate_subdir(subdir: str) -> str:
    """サブフォルダ名は単一階層のみ許可 (パストラバーサル防止)。"""
    if not subdir or "/" in subdir or subdir in (".", ".."):
        raise typer.BadParameter(f"subdir は単一フォルダ名 (got {subdir!r})")
    return subdir


def _local_subdir(kind: str, id_: str, subdir: str) -> Path:
    return REPO_ROOT / kind / id_ / subdir


def _gcs_subdir_uri(kind: str, id_: str, subdir: str) -> str:
    return f"{GCS_BUCKET}/{kind}/{id_}/{subdir}/"


def _check_gcloud() -> None:
    """gcloud が認証済みであることを確認。失敗したら exit 1。"""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        typer.echo("error: `gcloud` CLI が見つかりません", err=True)
        raise typer.Exit(code=1) from None
    except subprocess.TimeoutExpired:
        typer.echo("error: `gcloud auth list` がタイムアウトしました", err=True)
        raise typer.Exit(code=1) from None
    if result.returncode != 0 or not result.stdout.strip():
        typer.echo(
            "error: gcloud で認証済みアカウントが見つかりません。"
            "`gcloud auth login` を実行してください",
            err=True,
        )
        raise typer.Exit(code=1)


def _run_rsync(src: str, dst: str) -> int:
    """gcloud storage rsync を実行し戻り値を返す。stderr/stdout はそのまま流す。"""
    cmd = ["gcloud", "storage", "rsync", src, dst, "--recursive"]
    typer.echo(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd)


_TargetArg = Annotated[
    str,
    typer.Argument(
        help="<kind>/<theme>/<id> (e.g. profiles/2026-05-27_ASR-diarization/2026-05-30_parakeet)"
    ),
]

_SubdirOpt = Annotated[
    str,
    typer.Option(
        "--subdir",
        help="同期するサブフォルダ (default: results)。例: --subdir sidecars",
    ),
]


@app.command()
def upload(target: _TargetArg, subdir: _SubdirOpt = "results") -> None:
    """ローカルの <subdir>/ (default: results) を GCS にアップロード。"""
    kind, id_ = _split_target(target)
    _validate_subdir(subdir)
    _check_gcloud()
    src = _local_subdir(kind, id_, subdir)
    if not src.is_dir():
        typer.echo(f"error: {src} がありません", err=True)
        raise typer.Exit(code=1)
    if not any(src.iterdir()):
        typer.echo(f"warning: {src} が空です (upload をスキップ)", err=True)
        raise typer.Exit(code=0)
    dst = _gcs_subdir_uri(kind, id_, subdir)
    rc = _run_rsync(str(src) + "/", dst)
    if rc != 0:
        raise typer.Exit(code=rc)
    typer.echo(f"OK: uploaded → {dst}")


@app.command()
def download(target: _TargetArg, subdir: _SubdirOpt = "results") -> None:
    """GCS から <subdir>/ (default: results) をダウンロード。"""
    kind, id_ = _split_target(target)
    _validate_subdir(subdir)
    _check_gcloud()
    dst = _local_subdir(kind, id_, subdir)
    dst.mkdir(parents=True, exist_ok=True)
    src = _gcs_subdir_uri(kind, id_, subdir)
    rc = _run_rsync(src, str(dst) + "/")
    if rc != 0:
        raise typer.Exit(code=rc)
    typer.echo(f"OK: downloaded ← {src}")


@app.command(name="list")
def list_(target: _TargetArg, subdir: _SubdirOpt = "results") -> None:
    """GCS 側の <subdir>/ (default: results) のファイル一覧を表示。"""
    kind, id_ = _split_target(target)
    _validate_subdir(subdir)
    _check_gcloud()
    uri = _gcs_subdir_uri(kind, id_, subdir)
    cmd = ["gcloud", "storage", "ls", uri]
    typer.echo(f"$ {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    if rc != 0:
        raise typer.Exit(code=rc)


def _list_local_ids(kind: str) -> list[str]:
    """`<kind>/<theme>/<id>` の2階層を走査し `<theme>/<id>` 形式のリストを返す。"""
    parent = REPO_ROOT / kind
    if not parent.is_dir():
        return []
    ids: list[str] = []
    for theme_dir in parent.iterdir():
        if not theme_dir.is_dir() or theme_dir.name.startswith("."):
            continue
        for entry in theme_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                ids.append(f"{theme_dir.name}/{entry.name}")
    return sorted(ids)


def _bulk(action: str, kind_filter: str | None, subdir: str) -> None:
    _check_gcloud()
    kinds = VALID_KINDS if kind_filter is None else (kind_filter,)
    ok: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    for kind in kinds:
        for id_ in _list_local_ids(kind):
            target = f"{kind}/{id_}"
            typer.echo(f"\n--- {action} {target} ({subdir}) ---")
            if action == "upload":
                src = _local_subdir(kind, id_, subdir)
                if not src.is_dir() or not any(src.iterdir()):
                    typer.echo(f"  skip: {src} が空")
                    skipped.append(target)
                    continue
                rc = _run_rsync(str(src) + "/", _gcs_subdir_uri(kind, id_, subdir))
            else:  # download
                dst = _local_subdir(kind, id_, subdir)
                dst.mkdir(parents=True, exist_ok=True)
                rc = _run_rsync(_gcs_subdir_uri(kind, id_, subdir), str(dst) + "/")
            if rc == 0:
                ok.append(target)
            else:
                failed.append(target)
    typer.echo(f"\n=== summary ({action}) ===")
    typer.echo(f"OK:      {len(ok)}")
    typer.echo(f"skipped: {len(skipped)}")
    typer.echo(f"failed:  {len(failed)}")
    for t in failed:
        typer.echo(f"  - {t}")
    if failed:
        raise typer.Exit(code=1)


@app.command(name="upload-all")
def upload_all(
    kind: Annotated[
        str | None,
        typer.Option(help="experiments / profiles / analysis (省略時は全部)"),
    ] = None,
    subdir: _SubdirOpt = "results",
) -> None:
    """全 ID を一括 upload。"""
    if kind is not None and kind not in VALID_KINDS:
        raise typer.BadParameter(f"kind は {VALID_KINDS} のいずれか")
    _validate_subdir(subdir)
    _bulk("upload", kind, subdir)


@app.command(name="download-all")
def download_all(
    kind: Annotated[
        str | None,
        typer.Option(help="experiments / profiles / analysis (省略時は全部)"),
    ] = None,
    subdir: _SubdirOpt = "results",
) -> None:
    """全 ID を一括 download。"""
    if kind is not None and kind not in VALID_KINDS:
        raise typer.BadParameter(f"kind は {VALID_KINDS} のいずれか")
    _validate_subdir(subdir)
    _bulk("download", kind, subdir)


if __name__ == "__main__":
    app()
    sys.exit(0)
