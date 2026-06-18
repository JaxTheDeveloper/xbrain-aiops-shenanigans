#!/usr/bin/env python3
"""
closed_loop.py — Ronki closed-loop auto-remediation orchestrator.

Usage:
    python closed_loop.py --config config.yaml [--dry-run]

5 mandatory safety checkpoints every action must pass:
    1. Dry-run  2. Blast-radius  3. Decision validation
    4. Verify   5. Auto-rollback / Circuit-breaker

Stress features:
    - Per-service mutex: same service serialized, different services parallel
    - Transactional multi-step with ordered rollback
    - Runbook registry validation (hallucination guard)
"""

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

import requests
import yaml

from engine.logger import JsonLogger
from engine.metrics import (
    action_counter,
    blast_radius_gauge,
    circuit_breaker_gauge,
    mutex_gauge,
    start_metrics_server,
    verify_status_gauge,
)
from engine.safety import BlastRadiusGuard, CircuitBreaker
from engine.verify import verify_service

log = JsonLogger("orchestrator")

# ── Per-service mutex ─────────────────────────────────────────────────────────
_service_locks: dict[str, threading.Lock] = {}
_locks_meta = threading.Lock()


def get_service_lock(service: str) -> threading.Lock:
    with _locks_meta:
        if service not in _service_locks:
            _service_locks[service] = threading.Lock()
        return _service_locks[service]


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── Alertmanager polling ──────────────────────────────────────────────────────

def fetch_active_alerts(alertmanager_url: str) -> list[dict]:
    """Return active, non-silenced, non-inhibited alerts."""
    try:
        resp = requests.get(
            f"{alertmanager_url}/api/v2/alerts",
            params={"active": "true", "silenced": "false", "inhibited": "false"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.error("ALERTMANAGER_FETCH_ERROR", error=str(exc))
        return []


# ── Runbook execution ─────────────────────────────────────────────────────────

def _resolve_script(script_path: str) -> list[str]:
    """Return the correct interpreter + script path for the current platform.

    On Windows, .sh runbooks have a .ps1 sibling; use PowerShell for those.
    On Linux/Mac, use bash.
    """
    import platform
    p = Path(script_path)
    if platform.system() == "Windows":
        ps1 = p.with_suffix(".ps1")
        if ps1.exists():
            return ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)]
        # Fallback: try Git Bash if available
        return ["bash", script_path]
    return ["bash", script_path]


def run_runbook(script_and_args: str, service: str, dry_run: bool, timeout_s: int = 30) -> bool:
    """Execute a runbook script string (may include extra flags like --step-a or --step A).
    Returns True on exit code 0.
    """
    parts = script_and_args.split()
    script = parts[0]
    extra = parts[1:]  # e.g. ["--step-a"]

    interpreter = _resolve_script(script)

    # PowerShell scripts use -Service / -DryRun / -Step params
    import platform
    if platform.system() == "Windows" and interpreter[0] == "powershell":
        cmd = interpreter + ["-Service", service]
        # Translate --step-a → -Step A etc.
        for flag in extra:
            if flag == "--step-a":   cmd += ["-Step", "A"]
            elif flag == "--step-b": cmd += ["-Step", "B"]
            elif flag == "--step-c": cmd += ["-Step", "C"]
            elif flag == "--rollback-a": cmd += ["-Step", "RA"]
            elif flag == "--rollback-b": cmd += ["-Step", "RB"]
            else: cmd.append(flag)
        if dry_run:
            cmd.append("-DryRun")
    else:
        cmd = interpreter + ["--service", service] + extra
        if dry_run:
            cmd.append("--dry-run")

    log.info("RUNBOOK_EXEC", script=script_and_args, service=service, dry_run=dry_run)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        log.info("RUNBOOK_RESULT", script=script_and_args, service=service,
                 returncode=result.returncode,
                 stdout=result.stdout.strip()[:300],
                 stderr=result.stderr.strip()[:300])
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log.error("RUNBOOK_TIMEOUT", script=script_and_args, service=service, timeout_s=timeout_s)
        return False
    except Exception as exc:
        log.error("RUNBOOK_ERROR", script=script_and_args, service=service, error=str(exc))
        return False


# ── Decision helpers ──────────────────────────────────────────────────────────

def extract_service(alert: dict) -> str:
    labels = alert.get("labels", {})
    return labels.get("service") or labels.get("job") or "unknown"


def validate_runbook(runbook: str, cfg: dict, alertname: str) -> bool:
    """Reject runbook names not present in runbook_registry (hallucination guard)."""
    registry: list[str] = cfg.get("runbook_registry", list(cfg.get("runbook_map", {}).values()))
    if runbook in registry:
        return True
    log.error(
        "DECISION_VALIDATION_FAILED",
        bad_runbook=runbook,
        alertname=alertname,
        raw_decision=runbook,
        action="escalate_no_auto_action",
    )
    return False


# ── Transactional multi-step execution ───────────────────────────────────────

def run_transactional(
    steps: list[str],
    rollback_steps: list[str],
    service: str,
    timeout_s: int,
) -> bool:
    """Execute steps in order. On failure, run rollback_steps in the order listed.
    rollback_steps should already be in the correct rollback execution order (reverse of forward steps).
    Returns True only if all steps succeed.
    """
    completed: list[str] = []

    for step in steps:
        if not run_runbook(step, service, dry_run=False, timeout_s=timeout_s):
            log.error("TRANSACTIONAL_STEP_FAIL", step=step, service=service,
                      completed_before_failure=completed)
            # rollback_steps is ordered as: rollback of last completed step first
            # only run as many rollbacks as there were completed steps
            to_rollback = rollback_steps[: len(completed)]
            for rb in to_rollback:
                log.warning("TRANSACTIONAL_ROLLBACK_STEP", step=rb, service=service)
                run_runbook(rb, service, dry_run=False, timeout_s=timeout_s)
            log.info("TRANSACTIONAL_ROLLBACK_COMPLETE", service=service,
                     rolled_back=to_rollback)
            return False
        completed.append(step)

    return True


# ── Alert processing (all 5 checkpoints + stress features) ───────────────────

def process_alert(
    alert: dict,
    cfg: dict,
    baseline: dict,
    guard: BlastRadiusGuard,
    cb: CircuitBreaker,
    global_dry_run: bool,
):
    alertname = alert.get("labels", {}).get("alertname", "")
    service = extract_service(alert)

    log.info("ALERT_DETECTED", alertname=alertname, service=service,
             severity=alert.get("labels", {}).get("severity", ""))

    # Skip services explicitly excluded (e.g. the orchestrator itself)
    skip = cfg.get("skip_services", [])
    if service in skip:
        log.info("ALERT_SKIPPED", alertname=alertname, service=service,
                 reason="service in skip_services list")
        return

    # 1. DECIDE — map alert → runbook
    runbook = cfg["runbook_map"].get(alertname)
    if not runbook:
        log.warning("NO_RUNBOOK", alertname=alertname, service=service)
        return

    # Decision validation — reject hallucinated / unregistered runbook names
    if not validate_runbook(runbook, cfg, alertname):
        return

    log.info("DECIDE_RUNBOOK", alertname=alertname, service=service, runbook=runbook)

    # 2. BLAST-RADIUS check
    ok, reason = guard.check(service)
    if not ok:
        log.warning("BLAST_RADIUS_EXCEEDED", service=service, reason=reason)
        return
    log.info("BLAST_RADIUS_OK", service=service,
             remaining=guard.remaining_global())

    # Per-service mutex — serialize per service, allow parallel across services
    svc_lock = get_service_lock(service)
    acquired = svc_lock.acquire(blocking=False)
    if not acquired:
        log.warning("SERVICE_LOCK_BUSY", service=service,
                    message="Runbook already running for this service; skipping")
        return

    mutex_gauge.labels(service=service).set(1)
    try:
        _execute_alert(alert, alertname, service, runbook, cfg, baseline, guard, cb, global_dry_run)
    finally:
        mutex_gauge.labels(service=service).set(0)
        svc_lock.release()


def _execute_alert(
    alert: dict,
    alertname: str,
    service: str,
    runbook: str,
    cfg: dict,
    baseline: dict,
    guard: BlastRadiusGuard,
    cb: CircuitBreaker,
    global_dry_run: bool,
):
    timeout_s = cfg["runbook_timeout_seconds"]

    # 3. DRY-RUN — use first multi-step entry if available, otherwise the runbook itself
    multi_steps: list[str] = cfg.get("multi_step_map", {}).get(alertname, [])
    dry_run_script = multi_steps[0] if multi_steps else runbook
    if not run_runbook(dry_run_script, service, dry_run=True, timeout_s=timeout_s):
        log.error("DRY_RUN_FAIL", runbook=dry_run_script, service=service)
        return
    log.info("DRY_RUN_PASS", runbook=dry_run_script, service=service)

    # Global --dry-run: stop here, log and exit
    if global_dry_run:
        action_counter.labels(service=service, runbook=runbook, outcome="dry_run").inc()
        log.info("GLOBAL_DRY_RUN_SKIP", service=service,
                 message="--dry-run mode: no real action executed")
        return

    # Record action against blast-radius limits
    guard.record(service)
    blast_radius_gauge.labels(service=service).set(guard.remaining_global())

    # 4. ACT — single runbook or transactional multi-step
    if multi_steps:
        rollback_steps: list[str] = cfg.get("multi_step_rollback_map", {}).get(alertname, [])
        success = run_transactional(multi_steps, rollback_steps, service, timeout_s)
        if not success:
            cb.record_failure()
            circuit_breaker_gauge.labels(service=service).set(1 if cb.is_open() else 0)
            return
    else:
        if not run_runbook(runbook, service, dry_run=False, timeout_s=timeout_s):
            log.error("ACTION_EXEC_FAIL", runbook=runbook, service=service)
            cb.record_failure()
            circuit_breaker_gauge.labels(service=service).set(1 if cb.is_open() else 0)
            return

    log.info("ACTION_EXECUTED", alertname=alertname, service=service, runbook=runbook)

    # 5a. VERIFY — poll Prometheus
    t = baseline["verify_thresholds"]
    verify_status_gauge.labels(service=service, runbook=runbook).set(2)  # in_progress

    verify_ok = verify_service(
        prometheus_url=cfg["prometheus_url"],
        service=service,
        baseline=baseline,
        timeout_s=t["verify_timeout_seconds"],
        poll_interval_s=t["verify_poll_interval_seconds"],
        min_samples=t["verify_min_samples"],
    )

    if verify_ok:
        verify_status_gauge.labels(service=service, runbook=runbook).set(1)
        action_counter.labels(service=service, runbook=runbook, outcome="success").inc()
        cb.record_success()
        circuit_breaker_gauge.labels(service=service).set(0)
        log.info("ACTION_SUCCESS", alertname=alertname, service=service, runbook=runbook)
        return

    # 5b. AUTO-ROLLBACK on verify failure
    verify_status_gauge.labels(service=service, runbook=runbook).set(0)
    action_counter.labels(service=service, runbook=runbook, outcome="rollback").inc()

    rollback = cfg.get("rollback_map", {}).get(alertname, runbook)
    log.warning("ROLLBACK_TRIGGERED", service=service, alertname=alertname,
                rollback_runbook=rollback)
    run_runbook(rollback, service, dry_run=False, timeout_s=timeout_s)
    log.info("ROLLBACK_EXECUTED", service=service, rollback_runbook=rollback)

    cb.record_failure()
    circuit_breaker_gauge.labels(service=service).set(1 if cb.is_open() else 0)


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ronki closed-loop orchestrator")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect + decide only; no real actions executed")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Resolve baseline.json relative to the config file location
    baseline_path = Path(args.config).parent / cfg["baseline_path"]
    with open(baseline_path) as f:
        baseline = json.load(f)

    guard = BlastRadiusGuard(
        max_per_minute=cfg["blast_radius"]["max_actions_per_minute"],
        max_restarts_per_hour=cfg["blast_radius"]["max_restarts_per_service_per_hour"],
    )
    cb = CircuitBreaker(threshold=cfg["circuit_breaker"]["consecutive_failure_threshold"])

    # Fingerprint dedup — skip alerts already being actively processed
    # We do NOT permanently skip fingerprints so recurring alerts re-trigger correctly
    active: set[str] = set()
    active_lock = threading.Lock()

    start_metrics_server()
    log.info("ORCHESTRATOR_START", config=args.config, dry_run=args.dry_run,
             poll_interval_s=cfg["poll_interval_seconds"])

    while True:
        if cb.is_open():
            log.error("CIRCUIT_BREAKER_HALT",
                      message="Circuit open - no actions will be taken. Restart to reset.")
            time.sleep(cfg["poll_interval_seconds"])
            continue

        alerts = fetch_active_alerts(cfg["alertmanager_url"])

        threads = []
        for alert in alerts:
            fp = alert.get("fingerprint", "")
            # Skip if this exact alert fingerprint is already being processed
            with active_lock:
                if fp and fp in active:
                    continue
                if fp:
                    active.add(fp)

            def _run(a, f):
                try:
                    process_alert(a, cfg, baseline, guard, cb, args.dry_run)
                finally:
                    with active_lock:
                        active.discard(f)

            t = threading.Thread(target=_run, args=(alert, fp), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        time.sleep(cfg["poll_interval_seconds"])


if __name__ == "__main__":
    main()
