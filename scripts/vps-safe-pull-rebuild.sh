#!/usr/bin/env bash
# Run on the VPS from the project root, e.g.:
#   cd /opt/plagsini-ev && bash scripts/vps-safe-pull-rebuild.sh
#
# Fixes: git pull blocked by local edits to docker-compose.prod.yml (e.g. port 8001).
# The same ports are already in the GitHub repo — stash local changes, pull, rebuild.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Stash local docker-compose.prod.yml if modified..."
if git diff --quiet docker-compose.prod.yml 2>/dev/null; then
  STASHED=0
  echo "    (no local changes)"
else
  git stash push -m "vps-docker-compose-$(date +%Y%m%d%H%M%S)" -- docker-compose.prod.yml
  STASHED=1
  echo "    stashed."
fi

echo "==> git pull origin main"
git pull origin main

if [ "$STASHED" = "1" ]; then
  echo "==> Stash contains your old compose. If pull already has 8001:8001, drop it: git stash drop"
  echo "    Or merge: git stash pop  (fix conflicts if any)"
fi

echo "==> docker compose build + up (charging-platform)"
docker compose -f docker-compose.prod.yml build charging-platform --no-cache
docker compose -f docker-compose.prod.yml up -d charging-platform --force-recreate

echo "==> Verify new Operations UI in container (online_only):"
if docker exec plagsini-api grep -q 'online_only=1' /app/templates/operations.html 2>/dev/null; then
  echo "    OK: deployment has online-only dropdown code."
else
  echo "    WARN: grep failed — check container name (plagsini-api) and paths."
fi

echo "Done."
