#!/bin/bash
# Download AMI **manual word annotations** (NXT) for cpWER/WER reference.
#
# pyannote/AMI-diarization-setup (download_ami.sh) only ships diarization RTTMs
# (speaker turns, no text). cpWER needs the actual transcribed words per speaker,
# which live in the AMI manual annotation corpus (NXT XML).
#
# Outputs:
#   data/raw/ami/transcripts/ami_public_manual_1.6.2/words/*.words.xml
#     (per meeting × agent A/B/C/D: <w> elements with text + start/end times)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$REPO_ROOT/data/raw/ami/transcripts"
ZIP_URL="https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip"
ZIP_PATH="$DEST/ami_public_manual_1.6.2.zip"

mkdir -p "$DEST"

if [ -d "$DEST/words" ] && compgen -G "$DEST/words/*.words.xml" > /dev/null; then
  echo "AMI word annotations already present in $DEST/words"
  exit 0
fi

echo "Downloading AMI manual annotations (NXT) ..."
curl -L --fail --continue-at - --show-error -o "$ZIP_PATH" "$ZIP_URL"

echo "Unzipping ..."
unzip -q -o "$ZIP_PATH" -d "$DEST"

echo "Done. words dir:"
ls "$DEST/words" | head
echo "... ($(ls "$DEST/words"/*.words.xml | wc -l | tr -d ' ') word files)"
