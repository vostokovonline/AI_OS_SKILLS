#!/usr/bin/env bash
set -e

ROOT="/home/onor/ai_os_final"
REPORT="/tmp/prompt_audit_$(date +%Y%m%d_%H%M%S).log"

echo "PROMPT AUDIT REPORT — $(date)" | tee "$REPORT"
echo "ROOT: $ROOT" | tee -a "$REPORT"
echo "---------------------------------------------" | tee -a "$REPORT"

# 1️⃣ Python / LangChain / LiteLLM prompts
echo -e "\n[1] Searching Python prompts (system/user/messages)..." | tee -a "$REPORT"

grep -RIn \
  --exclude-dir=infra \
  --exclude-dir=.git \
  --exclude-dir=postgres_data \
  --exclude-dir=neo4j_data \
  --exclude-dir=minio_data \
  --exclude-dir=milvus_data \
  -E \
  "system_prompt|system message|\"role\": \"system\"|role=\"system\"|messages\s*=\s*\[|prompt\s*=|ChatPromptTemplate|SystemMessage|HumanMessage" \
  "$ROOT" \
  | tee -a "$REPORT"

# 2️⃣ LangGraph / recursion-prone phrases
echo -e "\n[2] Searching recursion-inducing phrases..." | tee -a "$REPORT"

grep -RIn \
  --exclude-dir=infra \
  --exclude-dir=.git \
  -E \
  "rethink|reflect|iterate|continue thinking|add more|expand|recursive|while True|until done|no limit|keep going" \
  "$ROOT" \
  | tee -a "$REPORT"

# 3️⃣ YAML / config prompts (litellm, agents, policies)
echo -e "\n[3] Searching YAML / config prompts..." | tee -a "$REPORT"

grep -RIn \
  --exclude-dir=.git \
  -E \
  "prompt:|system:|instruction:|policy:|agent:" \
  "$ROOT/infra" "$ROOT/services" 2>/dev/null \
  | tee -a "$REPORT"

# 4️⃣ Extract nearby context (±5 lines) for critical hits
echo -e "\n[4] Context dump for system prompts..." | tee -a "$REPORT"

while IFS=: read -r file line rest; do
  echo -e "\n--- FILE: $file (line $line) ---" | tee -a "$REPORT"
  sed -n "$((line-5)),$((line+5))p" "$file" | tee -a "$REPORT"
done < <(
  grep -RIn \
    --exclude-dir=infra \
    --exclude-dir=.git \
    -E "\"role\": \"system\"|SystemMessage|system_prompt" \
    "$ROOT"
)

echo -e "\n---------------------------------------------" | tee -a "$REPORT"
echo "✅ Prompt audit completed." | tee -a "$REPORT"
echo "📄 Report saved to: $REPORT"

