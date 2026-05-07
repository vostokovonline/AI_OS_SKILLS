#!/usr/bin/env bash
set -e

ROOT="$(pwd)"
OUT="$ROOT/prompt_audit_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUT"/{full_files,extracts,reports}

echo "🔍 PROMPT AUDIT STARTED"
echo "Root: $ROOT"
echo "Output: $OUT"
echo

# ---------------------------------------
# 1. Patterns that indicate prompts
# ---------------------------------------
PATTERNS=(
  "system_prompt"
  "supervisor"
  "planner"
  "goal"
  "task"
  "prompt"
  "messages ="
  "langgraph"
  "recursion"
)

# ---------------------------------------
# 2. Search source files
# ---------------------------------------
echo "🔎 Searching for prompt-related code..."

FOUND_FILES=()

while IFS= read -r file; do
  for p in "${PATTERNS[@]}"; do
    if grep -qi "$p" "$file"; then
      FOUND_FILES+=("$file")
      break
    fi
  done
done < <(
  find "$ROOT/services" \
    -type f \( -name "*.py" -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" \) \
    2>/dev/null
)

# Deduplicate
FOUND_FILES=($(printf "%s\n" "${FOUND_FILES[@]}" | sort -u))

# ---------------------------------------
# 3. Copy full files
# ---------------------------------------
echo "📦 Copying full files..."
for f in "${FOUND_FILES[@]}"; do
  SAFE_NAME=$(echo "$f" | sed 's|/|__|g')
  cp "$f" "$OUT/full_files/$SAFE_NAME"
done

# ---------------------------------------
# 4. Extract prompt fragments
# ---------------------------------------
echo "✂ Extracting prompt fragments..."
for f in "${FOUND_FILES[@]}"; do
  SAFE_NAME=$(echo "$f" | sed 's|/|__|g')
  {
    echo "FILE: $f"
    echo "----------------------------------------"
    for p in "${PATTERNS[@]}"; do
      grep -ni -C 10 "$p" "$f" || true
    done
    echo
  } > "$OUT/extracts/$SAFE_NAME.txt"
done

# ---------------------------------------
# 5. Generate report
# ---------------------------------------
REPORT="$OUT/reports/REPORT.md"

{
  echo "# PROMPT AUDIT REPORT"
  echo
  echo "Date: $(date)"
  echo
  echo "## Files containing prompts"
  echo
  for f in "${FOUND_FILES[@]}"; do
    echo "- $f"
  done
  echo
  echo "## Next steps"
  echo "- Identify SYSTEM / SUPERVISOR prompts"
  echo "- Remove recursive self-invocation language"
  echo "- Enforce bounded goal policies"
  echo "- Separate BOUNDED vs SYSTEMIC goals"
} > "$REPORT"

echo
echo "✅ PROMPT AUDIT COMPLETE"
echo "📂 Output: $OUT"
echo "📄 Report: $REPORT"
