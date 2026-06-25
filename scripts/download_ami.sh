#!/bin/bash
# Download AMI corpus test split (Mix-Headset) for diarization baseline.
# - Audio:  Edinburgh AMI mirror (Mix-Headset, 1ch)
# - RTTM/UEM: pyannote/AMI-diarization-setup (only_words refs)
# Outputs:
#   data/raw/ami/audio/*.Mix-Headset.wav
#   data/raw/ami/rttm/*.rttm
#   data/raw/ami/uem/*.uem
#   data/raw/ami/setup/  (full clone, for lists/speakers)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data/raw/ami"
SETUP_REPO="https://github.com/pyannote/AMI-diarization-setup.git"
AUDIO_BASE="https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus"
SPLIT="${1:-test}"  # test / dev / train (default: test)

mkdir -p "$DATA_DIR/audio" "$DATA_DIR/rttm" "$DATA_DIR/uem"

# 1. Clone (or update) the setup repo for refs and meeting lists
if [ ! -d "$DATA_DIR/setup/.git" ]; then
  echo "Cloning AMI-diarization-setup..."
  git clone --depth 1 "$SETUP_REPO" "$DATA_DIR/setup"
else
  echo "AMI-diarization-setup already cloned."
fi

LIST_FILE="$DATA_DIR/setup/lists/${SPLIT}.meetings.txt"
RTTM_SRC="$DATA_DIR/setup/only_words/rttms/${SPLIT}"
UEM_SRC="$DATA_DIR/setup/uems/${SPLIT}"

[ -f "$LIST_FILE" ] || { echo "Missing $LIST_FILE"; exit 1; }

# 2. Copy reference RTTMs and UEMs
echo "Copying RTTMs and UEMs for split=$SPLIT..."
cp "$RTTM_SRC"/*.rttm "$DATA_DIR/rttm/"
if compgen -G "$UEM_SRC/*.uem" > /dev/null; then
  cp "$UEM_SRC"/*.uem "$DATA_DIR/uem/"
fi

# 3. Download Mix-Headset wavs
total=$(grep -c . "$LIST_FILE")
i=0
while IFS= read -r mtg; do
  [ -z "$mtg" ] && continue
  i=$((i + 1))
  wav="$DATA_DIR/audio/${mtg}.Mix-Headset.wav"
  if [ -s "$wav" ]; then
    echo "[$i/$total] ✓ $mtg (already exists, $(du -h "$wav" | cut -f1))"
    continue
  fi
  url="${AUDIO_BASE}/${mtg}/audio/${mtg}.Mix-Headset.wav"
  echo "[$i/$total] ↓ $mtg"
  curl -L --fail --continue-at - --silent --show-error -o "$wav" "$url"
done < "$LIST_FILE"

echo
echo "Done. Total size:"
du -sh "$DATA_DIR/audio" "$DATA_DIR/rttm" "$DATA_DIR/uem" "$DATA_DIR/setup"
