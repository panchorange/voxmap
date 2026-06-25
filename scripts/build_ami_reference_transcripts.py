"""AMI NXT word アノテーション (words/*.words.xml) → cpWER 用の参照転写を作る。

各 meeting × agent (A/B/C/D…) の words XML から `<w>` を集め、句読点 (punc="true") と
非単語 (vocalsound/gap/disfmarker) を除外して、**話者別の単語列 + 連結テキスト**を作る。
cpWER は話者を最適置換でマッチングするので、AMI の agent letter をそのまま話者ラベルに使う
(hypothesis 側 SPEAKER_xx との対応づけは不要)。

出力: data/raw/ami/ref_transcripts/<meeting>.json
  {"meeting", "by_speaker": {agent: text}, "words": [{text,start,end,speaker}, ...]}

Usage:
    uv run python scripts/build_ami_reference_transcripts.py            # test split 全部
    uv run python scripts/build_ami_reference_transcripts.py --split dev
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Annotated

import typer

REPO_ROOT = Path(__file__).resolve().parents[1]
WORDS_DIR = REPO_ROOT / "data/raw/ami/transcripts/words"
SPLIT_DIR = REPO_ROOT / "data/raw/ami/setup/lists"
OUT_DIR = REPO_ROOT / "data/raw/ami/ref_transcripts"

_WORDS_RE = re.compile(r"^(?P<meeting>[A-Z]+\d+[a-z])\.(?P<agent>[A-Z])\.words\.xml$")


def parse_words_file(path: Path) -> list[tuple[str, float, float]]:
    """words XML → [(text, start, end)]。句読点・非単語は除外。"""
    tree = ET.parse(path)
    out: list[tuple[str, float, float]] = []
    for el in tree.getroot():
        tag = el.tag.split("}")[-1]  # strip namespace
        if tag != "w" or el.get("punc") == "true":
            continue
        text = (el.text or "").strip()
        if not text:
            continue
        start = float(el.get("starttime", "0"))
        end = float(el.get("endtime", str(start)))
        out.append((text, start, end))
    return out


def build_meeting(meeting: str) -> dict | None:
    files = sorted(WORDS_DIR.glob(f"{meeting}.*.words.xml"))
    if not files:
        return None
    words: list[dict] = []
    by_speaker: dict[str, list[str]] = {}
    for f in files:
        m = _WORDS_RE.match(f.name)
        if not m:
            continue
        agent = m.group("agent")
        for text, start, end in parse_words_file(f):
            words.append({"text": text, "start": start, "end": end, "speaker": agent})
            by_speaker.setdefault(agent, []).append(text)
    words.sort(key=lambda w: w["start"])
    return {
        "meeting": meeting,
        "by_speaker": {spk: " ".join(toks) for spk, toks in by_speaker.items()},
        "words": words,
    }


def main(
    split: Annotated[str, typer.Option(help="AMI split (test/dev/train)")] = "test",
) -> None:
    meetings = [
        line.strip()
        for line in (SPLIT_DIR / f"{split}.meetings.txt").read_text().splitlines()
        if line.strip()
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    for meeting in meetings:
        ref = build_meeting(meeting)
        if ref is None:
            print(f"  WARN no words xml for {meeting}", file=sys.stderr)
            continue
        (OUT_DIR / f"{meeting}.json").write_text(json.dumps(ref, ensure_ascii=False))
        n_words = len(ref["words"])
        n_spk = len(ref["by_speaker"])
        print(f"  {meeting:8s} speakers={n_spk} words={n_words}")
        n_ok += 1
    print(f"\nwrote {n_ok}/{len(meetings)} → {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    typer.run(main)
