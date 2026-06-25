#!/bin/bash
# Download MSDWild diarization dataset (audio + RTTM references).
# - Audio: single Google Drive zip (~7.56GB) via gdown (large-file confirm token を gdown が処理)
# - RTTM:  X-LANCE/MSDWILD repo の rttms/{few.train,few.val,many.val}.rttm (split ごとの結合 rttm)
# License: MSDWild は **research-only** (repo の MSDWILD_license_agreement.pdf 参照)。
#
# Outputs (voxmap レイアウト, per-meeting rttm に分割):
#   data/raw/msdwild/audio/<split>/<id>.wav
#   data/raw/msdwild/rttm/<split>/<id>.rttm
#   data/raw/msdwild/lists/<split>.txt   (1 行 1 meeting id, 5 桁数字)
#
# Splits: few.train | few.val | many.val
#   MSDWild に公式 'test' split は無い。val 2 種が held-out 評価用。
#   AMI/VoxConverse の "test" 相当には many.val (多人数・難) または few.val を使う。
#
# Usage:
#   scripts/download_msdwild.sh              # all splits (few.train+few.val+many.val)
#   scripts/download_msdwild.sh many.val     # 指定 split のみ rttm/list/audio を整備
#   MAX_FILES=5 scripts/download_msdwild.sh many.val   # audio を先頭 5 件に絞る (動作確認用)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data/raw/msdwild"
RTTM_REPO="https://github.com/X-LANCE/MSDWILD.git"
GDRIVE_ID="1I5qfuPPGBM9keJKz0VN-OYEeRMJ7dgpl"
WAV_MD5="0057f82daaddf2ce993d1bf0679929c4"

SPLIT="${1:-all}"
MAX_FILES="${MAX_FILES:-0}"  # 0 = all

case "$SPLIT" in
  all) SPLITS=(few.train few.val many.val) ;;
  few.train|few.val|many.val) SPLITS=("$SPLIT") ;;
  *) echo "Invalid split: $SPLIT (use all | few.train | few.val | many.val)"; exit 1 ;;
esac

mkdir -p "$DATA_DIR/lists"

# 1. annotations repo (rttms/) を clone / 再利用
if [ ! -d "$DATA_DIR/annotations/.git" ]; then
  echo "Cloning MSDWILD annotations (rttms/)..."
  git clone --depth 1 "$RTTM_REPO" "$DATA_DIR/annotations"
else
  echo "MSDWILD annotations already cloned."
fi

# 2. audio zip を Google Drive から取得 (gdown; uv 経由で一時導入)
zip_path="$DATA_DIR/msdwild_wav.zip"
if [ ! -s "$zip_path" ]; then
  echo "Downloading MSDWild wavs (~7.56GB) from Google Drive via gdown..."
  uv run --with gdown gdown "https://drive.google.com/uc?id=${GDRIVE_ID}" -O "$zip_path"
else
  echo "Audio zip already downloaded ($(du -h "$zip_path" | cut -f1))."
fi

# md5 検証 (失敗しても警告のみ; ミラー差異を許容)
if command -v md5sum >/dev/null; then
  got="$(md5sum "$zip_path" | cut -d' ' -f1)"
  if [ "$got" = "$WAV_MD5" ]; then echo "md5 OK ($got)"; else echo "WARN: md5 mismatch (got $got, expected $WAV_MD5)"; fi
fi

# 3. 展開 (zip 内構成に依存しないよう find で wav を集める)
staging="$DATA_DIR/.extract"
if [ ! -d "$staging" ] || [ -z "$(find "$staging" -name '*.wav' -print -quit 2>/dev/null)" ]; then
  echo "Extracting wavs to staging..."
  rm -rf "$staging"; mkdir -p "$staging"
  if command -v unzip >/dev/null; then
    unzip -q -o "$zip_path" -d "$staging"
  else
    python3 -m zipfile -e "$zip_path" "$staging"
  fi
fi

# wav basename(拡張子なし) -> path の索引を作る
declare -A WAV_PATH
while IFS= read -r w; do
  WAV_PATH["$(basename "$w" .wav)"]="$w"
done < <(find "$staging" -name '*.wav')
echo "Indexed ${#WAV_PATH[@]} wav files from zip."

# 4. split ごとに rttm を id 単位へ分割し、list と audio を整備
for split in "${SPLITS[@]}"; do
  rttm_src="$DATA_DIR/annotations/rttms/${split}.rttm"
  [ -f "$rttm_src" ] || { echo "Missing $rttm_src"; exit 1; }

  rttm_out="$DATA_DIR/rttm/$split"
  audio_out="$DATA_DIR/audio/$split"
  rm -rf "$rttm_out" "$audio_out"; mkdir -p "$rttm_out" "$audio_out"

  echo "Splitting $rttm_src into per-meeting rttm..."
  # col2 = recording id。1 回の awk 内で id ごとのファイルに振り分ける。
  awk -v d="$rttm_out" '{print > (d"/"$2".rttm")}' "$rttm_src"

  # list は rttm に存在する id を昇順で
  ls "$rttm_out"/*.rttm | xargs -n1 basename | sed 's/\.rttm$//' | sort -u > "$DATA_DIR/lists/$split.txt"

  # MAX_FILES で list を絞る (audio コピー量も削減; 動作確認用)
  if [ "$MAX_FILES" -gt 0 ]; then
    head -n "$MAX_FILES" "$DATA_DIR/lists/$split.txt" > "$DATA_DIR/lists/$split.txt.tmp"
    mv "$DATA_DIR/lists/$split.txt.tmp" "$DATA_DIR/lists/$split.txt"
  fi

  # list の id に対応する wav を audio_out へ配置 (見つからなければ警告)
  missing=0; placed=0
  while IFS= read -r mid; do
    src="${WAV_PATH[$mid]:-}"
    if [ -n "$src" ] && [ -f "$src" ]; then
      cp -f "$src" "$audio_out/$mid.wav"; placed=$((placed+1))
    else
      echo "  WARN: no wav for id=$mid"; missing=$((missing+1))
    fi
  done < "$DATA_DIR/lists/$split.txt"
  echo "  split=$split: rttm=$(ls "$rttm_out"/*.rttm | wc -l) audio=$placed missing=$missing list=$(wc -l < "$DATA_DIR/lists/$split.txt")"
done

# 5. staging は audio をコピー済みなので破棄 (zip は再実行用に残す)
rm -rf "$staging"

echo
echo "Done. Sizes:"
du -sh "$DATA_DIR/audio" "$DATA_DIR/rttm" 2>/dev/null || true
