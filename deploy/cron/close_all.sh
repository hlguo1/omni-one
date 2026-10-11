#!/bin/sh
# close_all.sh — loop shops dir, run `omni-one close` per shop, write manifest.csv.
# POSIX sh only (no bashisms: no arrays, no [[, no function keyword, no &>).
# Env: SHOPS_DIR (default ./data/shops), CLOSE_OUT (default ./data/closes),
#      OMNI_ONE_BIN (default omni-one), CLOSE_SEED (default 42).
set -eu

SHOPS_DIR="${SHOPS_DIR:-./data/shops}"
CLOSE_OUT="${CLOSE_OUT:-./data/closes}"
OMNI_ONE_BIN="${OMNI_ONE_BIN:-omni-one}"
CLOSE_SEED="${CLOSE_SEED:-42}"

mkdir -p "$SHOPS_DIR" "$CLOSE_OUT"
MANIFEST="$CLOSE_OUT/manifest.csv"
TODAY="$(date +%F)"

if [ ! -f "$MANIFEST" ]; then
  printf 'date,shop,status,out_dir,note\n' > "$MANIFEST"
fi

found=0
for shop_path in "$SHOPS_DIR"/*; do
  [ -d "$shop_path" ] || continue
  found=1
  shop="$(basename "$shop_path")"
  out="$CLOSE_OUT/$TODAY-$shop"
  mkdir -p "$out"
  if "$OMNI_ONE_BIN" close --folder "$shop_path" --shop "$shop" --seed "$CLOSE_SEED" --out "$out" > "$out/close.log" 2>&1; then
    status="ok"
    note=""
  else
    # fall back to demo close so one bad folder never kills the whole run
    if "$OMNI_ONE_BIN" close --demo --shop "$shop" --seed "$CLOSE_SEED" --out "$out" > "$out/close.log" 2>&1; then
      status="demo-fallback"
      note="folder close failed; demo used"
    else
      status="failed"
      note="see close.log"
    fi
  fi
  # csv-escape: strip commas/newlines from note (POSIX tr)
  note="$(printf '%s' "$note" | tr ',;\n' '   ')"
  printf '%s,%s,%s,%s,%s\n' "$TODAY" "$shop" "$status" "$out" "$note" >> "$MANIFEST"
  echo "close_all: $shop -> $status ($out)"
done

if [ "$found" -eq 0 ]; then
  echo "close_all: no shops in $SHOPS_DIR (add one folder per shop)" >&2
fi
echo "close_all: manifest $MANIFEST"

# SHOP_LOCALE: draft language for all shops (en|es|zh|fr|de, default en).
# Numbers never change with locale. Example: SHOP_LOCALE=es ./close_all.sh
