"""Check consistency between repo, Obsidian docs, _index.md, and GCS.

Usage:
    uv run python scripts/sync_check.py [--kind experiments|profiles|all]

実体は以下の4つの整合性チェック:
  1. repo (experiments/<id>/ または profiles/<id>/) が存在するか
  2. Obsidian docs (docs/experiments/<id>.md / docs/profiles/<id>.md) が存在するか
  3. _index.md に <id> への参照があるか
  4. ローカル results/metrics.json が存在するか
  5. GCS (gs://voxmap/<kind>/<id>/results/) が存在するか

gcloud が無い・認証されていない場合は GCS 列を `-` で表示してそのまま続行する。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import typer

REPO_ROOT = Path(__file__).resolve().parents[1]
GCS_BUCKET = "gs://voxmap"

KINDS: dict[str, dict[str, Path]] = {
    "experiments": {
        "repo": REPO_ROOT / "experiments",
        "docs": REPO_ROOT / "docs" / "experiments",
    },
    "profiles": {
        "repo": REPO_ROOT / "profiles",
        "docs": REPO_ROOT / "docs" / "profiles",
    },
    "analysis": {
        "repo": REPO_ROOT / "analysis",
        "docs": REPO_ROOT / "docs" / "analysis",
    },
}

app = typer.Typer(add_completion=False)


@dataclass
class CheckResult:
    kind: str
    id: str
    has_repo: bool = False
    has_doc: bool = False
    in_index: bool = False
    has_local_results: bool = False  # experiments: metrics.json / profiles: results/ 非空
    has_gcs: bool | None = None  # None = unknown (gcloud unavailable)
    notes: list[str] = field(default_factory=list)
    repo_path: Path | None = None  # experiments は theme/<id> の full path

    def is_ok(self) -> bool:
        return (
            self.has_repo
            and self.has_doc
            and self.in_index
            and self.has_local_results
            and (self.has_gcs is None or self.has_gcs)
        )


def list_dir_ids(parent: Path) -> set[str]:
    if not parent.is_dir():
        return set()
    return {
        p.name
        for p in parent.iterdir()
        if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("__")
    }


def list_themed_ids(parent: Path) -> dict[str, Path]:
    """theme/<id>/ の2階層構造を {id: full_path} で返す (experiments/profiles/analysis 共通)。"""
    if not parent.is_dir():
        return {}
    result: dict[str, Path] = {}
    for theme_dir in parent.iterdir():
        if not theme_dir.is_dir() or theme_dir.name.startswith("."):
            continue
        for entry in theme_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                result[entry.name] = entry
    return result


def list_doc_ids(docs_dir: Path) -> set[str]:
    if not docs_dir.is_dir():
        return set()
    # テーマサブディレクトリ配下の *.md も含む
    direct = {p.stem for p in docs_dir.glob("*.md") if not p.name.startswith("_")}
    themed = {p.stem for p in docs_dir.glob("*/*.md") if not p.name.startswith("_")}
    return direct | themed


_ID_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_[\w\-]+$")


def parse_index_ids(index_path: Path) -> set[str]:
    """Extract IDs from wiki links `[[<id>]]` in _index.md.

    `<id>` は `YYYY-MM-DD_<name>` 形式のみ受理する (テンプレリンクや相対パスを弾く)。
    """
    if not index_path.exists():
        return set()
    text = index_path.read_text(encoding="utf-8")
    candidates = re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]", text)
    return {c for c in candidates if _ID_PATTERN.match(c)}


def has_local_results(kind: str, repo_path: Path) -> bool:
    """ローカルに結果ファイルがあるか。experiments は metrics.json、profiles は results/ 非空。"""
    results_dir = repo_path / "results"
    if not results_dir.is_dir():
        return False
    if kind == "experiments":
        return (results_dir / "metrics.json").exists()
    return any(results_dir.iterdir())


def list_gcs_ids(kind: str) -> set[str] | None:
    """List `<id>` dirs under gs://voxmap/<kind>/<theme>/. Returns None if gcloud unavailable.

    GCS は repo と同じ `<kind>/<theme>/<id>/` の2階層構造なので、theme 階層を1つ
    潜って `<id>` を集める (theme 名を id と誤認しないように)。
    """
    try:
        result = subprocess.run(
            # `*/` で theme 階層を展開し、その配下の `<id>/` を列挙する
            ["gcloud", "storage", "ls", f"{GCS_BUCKET}/{kind}/*/"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        # バケットに該当 kind が一切無い場合も非0になりうる。空集合として扱う。
        return set()
    ids: set[str] = set()
    for raw in result.stdout.splitlines():
        line = raw.strip().rstrip("/")
        if not line or not line.startswith(GCS_BUCKET):
            continue
        leaf = line.rsplit("/", 1)[-1]
        # `gs://voxmap/<kind>/<theme>:` のような見出し行や theme 自体を除き、id だけ残す
        if _ID_PATTERN.match(leaf):
            ids.add(leaf)
    return ids


def collect(kind: str) -> tuple[list[CheckResult], list[str]]:
    """Return (results, warnings)."""
    paths = KINDS[kind]
    doc_ids = list_doc_ids(paths["docs"])
    index_ids = parse_index_ids(paths["docs"] / "_index.md")
    gcs_ids = list_gcs_ids(kind)

    # 全 kind が theme/<id> の2階層構造
    themed_map = list_themed_ids(paths["repo"])
    exp_map = themed_map if themed_map else None
    repo_ids = set(themed_map.keys())

    warnings: list[str] = []
    all_ids = repo_ids | doc_ids | index_ids
    if gcs_ids is not None:
        all_ids |= gcs_ids

    results: list[CheckResult] = []
    for id_ in sorted(all_ids):
        r = CheckResult(kind=kind, id=id_)
        r.has_repo = id_ in repo_ids
        r.has_doc = id_ in doc_ids
        r.in_index = id_ in index_ids
        if r.has_repo:
            full_path = exp_map[id_] if exp_map else paths["repo"] / id_
            r.repo_path = full_path
            r.has_local_results = has_local_results(kind, full_path)
        if gcs_ids is not None:
            r.has_gcs = id_ in gcs_ids
        results.append(r)

    if gcs_ids is None:
        warnings.append(
            f"GCS の確認をスキップ ({kind}): "
            "`gcloud` が無い / 認証されていない / バケットにアクセスできない"
        )
    return results, warnings


def mark(value: bool | None) -> str:
    if value is None:
        return "-"
    return "OK" if value else "MISS"


def render_table(results: list[CheckResult], kind: str) -> str:
    local_col = "metrics.json" if kind == "experiments" else "results/"
    lines = [
        f"| id | repo | doc | index | {local_col} | GCS |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.id} | {mark(r.has_repo)} | {mark(r.has_doc)} | {mark(r.in_index)} | "
            f"{mark(r.has_local_results) if r.has_repo else '-'} | {mark(r.has_gcs)} |"
        )
    return "\n".join(lines)


def render_report(all_results: dict[str, list[CheckResult]], warnings: list[str]) -> str:
    sections: list[str] = ["# sync_check report\n"]
    if warnings:
        sections.append("## 注意")
        for w in warnings:
            sections.append(f"- {w}")
        sections.append("")
    for kind, results in all_results.items():
        sections.append(f"## {kind}")
        if not results:
            sections.append("(エントリ無し)\n")
            continue
        ok = sum(1 for r in results if r.is_ok())
        sections.append(f"{ok} / {len(results)} OK\n")
        sections.append(render_table(results, kind))
        sections.append("")
        bad = [r for r in results if not r.is_ok()]
        if bad:
            sections.append("### 不整合の修正候補")
            for r in bad:
                fixes = suggest_fixes(r)
                if fixes:
                    sections.append(f"- **{r.id}**")
                    sections.extend(f"  - {f}" for f in fixes)
            sections.append("")
    return "\n".join(sections)


def suggest_fixes(r: CheckResult) -> list[str]:
    fixes: list[str] = []
    docs_dir = KINDS[r.kind]["docs"].relative_to(REPO_ROOT)
    repo_dir = KINDS[r.kind]["repo"].relative_to(REPO_ROOT)
    rel_path = r.repo_path.relative_to(REPO_ROOT) if r.repo_path else Path(f"{repo_dir}/{r.id}")
    if not r.has_repo and r.has_doc:
        fixes.append(f"repo に `{rel_path}/` が無い。docs が古いか repo を作り忘れている")
    if not r.has_repo and r.in_index:
        fixes.append(f"`{docs_dir}/_index.md` に記載があるが repo に dir が無い (ID 名のズレ?)")
    if r.has_repo and not r.has_doc:
        fixes.append(f"`{docs_dir}/{r.id}.md` を作成する (考察ノート用)")
    if r.has_repo and not r.in_index:
        fixes.append(f"`{docs_dir}/_index.md` に `[[{r.id}]]` を追記する")
    if r.has_repo and not r.has_local_results:
        if r.kind == "experiments":
            msg = f"`{rel_path}/results/metrics.json` が無い"
        else:
            msg = f"`{rel_path}/results/` が空"
        fixes.append(f"{msg}。`sync-results` で GCS から download するか再実行する")
    if r.has_repo and r.has_gcs is False:
        fixes.append(f"`sync-results upload {r.kind}/{r.id}` で GCS にアップロード")
    if not r.has_repo and r.has_gcs:
        fixes.append("GCS には残っているが local に repo dir が無い (削除済み?)")
    return fixes


@app.command()
def main(
    kind: Annotated[
        str,
        typer.Option(help="experiments / profiles / analysis / all"),
    ] = "all",
) -> None:
    if kind not in ("experiments", "profiles", "analysis", "all"):
        raise typer.BadParameter("kind must be experiments / profiles / analysis / all")
    targets = ["experiments", "profiles", "analysis"] if kind == "all" else [kind]
    all_results: dict[str, list[CheckResult]] = {}
    warnings: list[str] = []
    for k in targets:
        results, w = collect(k)
        all_results[k] = results
        warnings.extend(w)
    report = render_report(all_results, warnings)
    typer.echo(report)
    # 不整合があれば exit 1 (CI / make から呼ぶとき用)
    has_issue = any(not r.is_ok() for results in all_results.values() for r in results)
    raise typer.Exit(code=1 if has_issue else 0)


if __name__ == "__main__":
    app()
