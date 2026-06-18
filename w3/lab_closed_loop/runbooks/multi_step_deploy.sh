#!/usr/bin/env bash
# multi_step_deploy.sh — 3-step transactional deploy with rollback support
#
# Steps:  A (drain) → B (apply config) → C (re-enable traffic)
# Rollbacks run in REVERSE: rollback-B then rollback-A
#
# Usage:
#   bash multi_step_deploy.sh --service <name> --step-a|--step-b|--step-c [--dry-run]
#   bash multi_step_deploy.sh --service <name> --rollback-b|--rollback-a  [--dry-run]
#
# Exit: 0=success, 1=failure

set -euo pipefail

SERVICE=""
DRY_RUN=false
STEP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)    SERVICE="$2"; shift 2 ;;
    --dry-run)    DRY_RUN=true; shift ;;
    --step-a)     STEP="A";  shift ;;
    --step-b)     STEP="B";  shift ;;
    --step-c)     STEP="C";  shift ;;
    --rollback-b) STEP="RB"; shift ;;
    --rollback-a) STEP="RA"; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

[[ -z "$SERVICE" ]] && { echo "ERROR: --service required"; exit 1; }

CONTAINER="ronki-${SERVICE}"

if $DRY_RUN; then
  echo "[DRY-RUN] would execute: multi_step_deploy step=$STEP on $CONTAINER"
  exit 0
fi

case "$STEP" in
  A)
    echo "[multi_step_deploy] step-A: draining $CONTAINER..."
    docker stop "$CONTAINER" 2>/dev/null || true
    echo "[multi_step_deploy] step-A done."
    ;;
  B)
    echo "[multi_step_deploy] step-B: applying config to $CONTAINER..."
    docker restart "$CONTAINER" 2>/dev/null || docker start "$CONTAINER"
    sleep 3
    STATUS=$(docker inspect --format '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo "missing")
    [[ "$STATUS" == "running" ]] || { echo "ERROR: step-B failed — status=$STATUS"; exit 1; }
    echo "[multi_step_deploy] step-B done."
    ;;
  C)
    echo "[multi_step_deploy] step-C: re-enabling traffic for $CONTAINER..."
    docker start "$CONTAINER" 2>/dev/null || true
    sleep 2
    STATUS=$(docker inspect --format '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo "missing")
    [[ "$STATUS" == "running" ]] || { echo "ERROR: step-C failed — status=$STATUS"; exit 1; }
    echo "[multi_step_deploy] step-C done."
    ;;
  RB)
    echo "[multi_step_deploy] rollback-B: reverting config on $CONTAINER..."
    docker restart "$CONTAINER" 2>/dev/null || docker start "$CONTAINER"
    sleep 3
    echo "[multi_step_deploy] rollback-B done."
    ;;
  RA)
    echo "[multi_step_deploy] rollback-A: restoring traffic to $CONTAINER..."
    docker start "$CONTAINER" 2>/dev/null || true
    sleep 2
    echo "[multi_step_deploy] rollback-A done."
    ;;
  *)
    echo "ERROR: specify --step-a/b/c or --rollback-a/b"
    exit 1
    ;;
esac

exit 0
