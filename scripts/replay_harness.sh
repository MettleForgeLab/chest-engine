#!/usr/bin/env bash
set -euo pipefail

CHEST_BASE="${CHEST_BASE:-http://localhost:7080}"
RUNS="${RUNS:-2}"
PROMPT="${PROMPT:-Describe warmth in five words.}"
SEED="${SEED:-123456}"

need(){ command -v "$1" >/dev/null 2>&1 || { echo "missing $1"; exit 1; }; }
need curl
need python3

hashes=()
for i in $(seq 1 "$RUNS"); do
  payload=$(python3 - <<PY
import json
print(json.dumps({"case_id":f"replay_{i}","input_text":${PROMPT@Q},"seed":int(${SEED})}))
PY
)
  resp="$(curl -sS -X POST "$CHEST_BASE/replay/run" -H "Content-Type: application/json" --data-binary "$payload")"
  h="$(python3 - <<'PY'
import json, sys
obj=json.loads(sys.stdin.read())
print(obj.get("commit_hash",""))
PY
<<<"$resp")"
  test -n "$h" || { echo "missing commit_hash"; echo "$resp"; exit 1; }
  hashes+=("$h")
done

base="${hashes[0]}"
for h in "${hashes[@]}"; do
  [[ "$h" == "$base" ]] || { echo "replay mismatch"; printf '%s\n' "${hashes[@]}"; exit 1; }
done
echo "PASS"