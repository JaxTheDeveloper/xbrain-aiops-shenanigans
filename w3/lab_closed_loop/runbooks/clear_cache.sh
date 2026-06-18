#!/usr/bin/env bash
# clear_cache.sh — flush service cache via SIGHUP
# Usage: bash clear_cache.sh --service <name> [--dry-run]
# Exit: 0=success, 1=failure

set -euo pipefail

SERVICE=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)  SERVICE="$2"; shift 2 ;;
    --dry-run)  DRY_RUN=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

[[ -z "$SERVICE" ]] && { echo "ERROR: --service required"; exit 1; }

CONTAINER="ronki-${SERVICE}"

if $DRY_RUN; then
  echo "[DRY-RUN] would execute: docker kill --signal=SIGHUP $CONTAINER"
  exit 0
fi

if ! docker inspect "$CONTAINER" > /dev/null 2>&1; then
  echo "[clear_cache] ERROR: container $CONTAINER not found."
  exit 1
fi

echo "[clear_cache] Sending SIGHUP to $CONTAINER..."
docker kill --signal=SIGHUP "$CONTAINER"
echo "[clear_cache] Cache flush triggered on $CONTAINER."
exit 0
