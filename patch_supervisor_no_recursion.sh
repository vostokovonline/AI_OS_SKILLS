#!/bin/bash

ROOT="/home/onor/ai_os_final"
REPORT="$ROOT/patch_report_supervisor.txt"
DATE=$(date +"%Y-%m-%d %H:%M:%S")

echo "PATCH REPORT — $DATE" > "$REPORT"
echo "---------------------------------" >> "$REPORT"

FOUND=0

search_and_patch() {
  FILE="$1"

  if grep -q "recursion_limit" "$FILE"; then
    echo "✔ Found recursion logic in $FILE" >> "$REPORT"
    cp "$FILE" "$FILE.bak"

    sed -i '/recursion_limit/d' "$FILE"
    sed -i '/recurse/d' "$FILE"
    sed -i '/self.run()/d' "$FILE"

    echo "✔ Patched $FILE (backup created)" >> "$REPORT"
    FOUND=1
  fi
}

while IFS= read -r -d '' file; do
  search_and_patch "$file"
done < <(find "$ROOT" -type f -name "*.py" -print0)

if [ "$FOUND" -eq 0 ]; then
  echo "⚠ No supervisor recursion logic found" >> "$REPORT"
fi

echo "---------------------------------" >> "$REPORT"
echo "DONE" >> "$REPORT"

cat "$REPORT"
