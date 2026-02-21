#!/usr/bin/env bash
set -euo pipefail
echo "[det] chest-engine checks"

req=(
  "forge-deps.yaml"
  "schemas/commit_record.schema.json"
  "docs/REPLAY_ENDPOINT.md"
  "docs/EVENT_MEMBRANE.md"
  "docs/COMMIT_RECORD.md"
  "scripts/replay_harness.sh"
)

missing=()
for f in "${req[@]}"; do
  [[ -f "$f" ]] || missing+=("$f")
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "[det] FAIL missing files:"
  printf '  - %s\n' "${missing[@]}"
  exit 1
fi

echo "[det] OK"