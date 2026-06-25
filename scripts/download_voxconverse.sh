#!/bin/bash
# Download VoxConverse diarization dataset (audio + RTTM references).
# - Audio: VGG Oxford mirror (voxconverse_<split>_wav.zip)
# - RTTM:  joonson/voxconverse GitHub repo (master = v0.3, test rttm の既知バグ修正済み)
# Outputs:
#   data/raw/voxconverse/audio/<split>/*.wav
#   data/raw/voxconverse/rttm/<split>/*.rttm
#   data/raw/voxconverse/lists/<split>.txt   (1 行 1 meeting id)
#
# 規模: dev=216 files (~2.0GB zip), test=232 files (~4.3GB zip)
#
# Usage:
#   scripts/download_voxconverse.sh         # dev (default)
#   scripts/download_voxconverse.sh test    # test
#   MAX_FILES=5 scripts/download_voxconverse.sh dev   # audio を先頭 5 件だけに絞る (動作確認用)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data/raw/voxconverse"
RTTM_REPO="https://github.com/joonson/voxconverse.git"
AUDIO_BASE="https://www.robots.ox.ac.uk/~vgg/data/voxconverse/data"
SPLIT="${1:-dev}"
MAX_FILES="${MAX_FILES:-0}"  # 0 = all

case "$SPLIT" in
  dev|test) ;;
  *) echo "Invalid split: $SPLIT (use 'dev' or 'test')"; exit 1 ;;
esac

mkdir -p "$DATA_DIR/rttm/$SPLIT" "$DATA_DIR/audio/$SPLIT" "$DATA_DIR/lists"

# 1. Clone (or reuse) the annotation repo for RTTM refs
if [ ! -d "$DATA_DIR/annotations/.git" ]; then
  echo "Cloning voxconverse annotations (master = v0.3)..."
  git clone --depth 1 "$RTTM_REPO" "$DATA_DIR/annotations"
else
  echo "voxconverse annotations already cloned."
fi

RTTM_SRC="$DATA_DIR/annotations/$SPLIT"
[ -d "$RTTM_SRC" ] || { echo "Missing $RTTM_SRC"; exit 1; }

# 2. Copy RTTMs and build the meeting list
echo "Copying RTTMs for split=$SPLIT..."
cp "$RTTM_SRC"/*.rttm "$DATA_DIR/rttm/$SPLIT/"
ls "$DATA_DIR/rttm/$SPLIT"/*.rttm | xargs -n1 basename | sed 's/\.rttm$//' | sort > "$DATA_DIR/lists/$SPLIT.txt"
total=$(wc -l < "$DATA_DIR/lists/$SPLIT.txt")
echo "Found $total meetings for split=$SPLIT"

# 3. Download audio zip (resumable)
zip_path="$DATA_DIR/voxconverse_${SPLIT}_wav.zip"
url="${AUDIO_BASE}/voxconverse_${SPLIT}_wav.zip"
if [ ! -s "$zip_path" ]; then
  echo "Downloading $url (large: dev~2.0GB / test~4.3GB)..."
  curl -L --fail --continue-at - --progress-bar -o "$zip_path" "$url"
else
  echo "Audio zip already downloaded ($(du -h "$zip_path" | cut -f1))."
fi

# 4. Extract to flat layout (zip 内のフォルダ構成に依存しないよう find で wav を集める)
echo "Extracting audio to $DATA_DIR/audio/$SPLIT/ ..."
tmp_extract="$DATA_DIR/.extract_$SPLIT"
rm -rf "$tmp_extract"; mkdir -p "$tmp_extract"
if command -v unzip >/dev/null; then
  unzip -q -o "$zip_path" -d "$tmp_extract"
else
  python3 -m zipfile -e "$zip_path" "$tmp_extract"
fi
find "$tmp_extract" -name '*.wav' -exec mv -f -t "$DATA_DIR/audio/$SPLIT/" {} +
rm -rf "$tmp_extract"

# 5. Optionally trim audio to MAX_FILES (動作確認用; rttm/list は全件のまま残す点に注意)
if [ "$MAX_FILES" -gt 0 ]; then
  echo "MAX_FILES=$MAX_FILES: trimming audio dir to first $MAX_FILES files..."
  keep=$(head -n "$MAX_FILES" "$DATA_DIR/lists/$SPLIT.txt")
  for wav in "$DATA_DIR/audio/$SPLIT"/*.wav; do
    id=$(basename "$wav" .wav)
    echo "$keep" | grep -qx "$id" || rm -f "$wav"
  done
fi

echo
echo "Done. Sizes:"
du -sh "$DATA_DIR/audio/$SPLIT" "$DATA_DIR/rttm/$SPLIT"
echo "audio wavs: $(ls "$DATA_DIR/audio/$SPLIT"/*.wav 2>/dev/null | wc -l) / list ids: $total"
