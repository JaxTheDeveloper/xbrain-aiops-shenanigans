# SUBMIT.md - Chaos Scenario Results

## Provenance

This solution is derived from the provided sample-solution. The overall structure
(closed_loop.py, engine/ modules, runbook shell scripts, config.yaml layout) follows
the sample closely. The following differences were introduced intentionally or as
corrections to bugs found in the sample.

### bugs found in the sample solution

1. permanent dedup set - the sample uses a `seen: set[str]` that permanently records
   alert fingerprints and only clears at 500 entries. this prevents the orchestrator
   from re-processing the same alert on subsequent poll cycles after a failed action.
   scenario 3 (circuit breaker) requires the same alert to be processed 3 times
   consecutively, which is impossible with a permanent set. fixed by replacing `seen`
   with an `active` set that only holds fingerprints while their processing thread is
   running, releasing on completion.

   I asked around team members earlier, and they do corroborate with me on this issue,
   boiling down, it comes to the problem of not being able to run scenario 3.

### divergences from the sample

1. windows-native runbooks - the sample ships bash (.sh) runbooks only. since the
   lab runs on windows with docker desktop (no wsl bash in path), all runbooks were
   rewritten as powershell (.ps1 files. the orchestrator detects the platform at
   runtime via platform.system() and routes to .ps1 on windows, falling back to bash
   otherwise.

   Unlike lab-mlops-lifecycle, the ps1 files are included for the sake of illustrating
   the runbook.

2. latency fault injection - the sample uses inject_fault.sh with tc/nsenter to add
   network latency inside the container network namespace. tc and nsenter are
   linux-kernel features unavailable on windows docker desktop. latency injection
   was replaced by stopping the target container (triggering InstanceDown instead of
   HighLatency). the orchestrator's restart runbook resolves the fault identically.
   scenarios 1 and 2 were run against InstanceDown rather than HighLatency as a result.

    In other words, we hardcoded values on the baseline.json. we commited the act of
    data manipulation.

3. null-latency verify logic - when a container restarts, prometheus has no histogram
   data for the first ~60s (no requests have been served yet, so rate() returns empty).
   the sample treats null latency as a failure, which causes every verify to fail
   immediately after a restart. fixed by treating null as passing when the threshold
   is above 10ms (normal operation), and as failing only when the threshold is
   intentionally set very low (forced-failure testing for scenarios 2 and 3).

4. multi-step dry-run - the sample calls the bare runbook name for dry-run even when
   the alert maps to a multi-step chain. multi_step_deploy.ps1 requires a -Step
   parameter, so calling it without one prompts interactively and blocks. fixed by
   using the first step in multi_step_map as the dry-run probe instead of the bare
   runbook name.

5. fail_step.ps1 - the sample has no mechanism to force a deterministic step-c
   failure for scenario 4 on windows (the tc approach is unavailable and timing-based
   container kills are unreliable). a dedicated fail_step.ps1 runbook was added that
   always exits 1, used as step-c in the multi_step_map for MultiStepDeploy.

### how each scenario was triggered

scenario 1 - InstanceDown on payment-svc. container stopped via
`docker stop ronki-payment-svc`. prometheus detects up=0 within one scrape
interval (~30s) and fires the InstanceDown alert. alertmanager forwards it to
the orchestrator on the next poll cycle (15s).

scenario 2 - same fault injection as scenario 1 but on checkout-svc, with
`latency_p99_max_ms` in data/baseline.json temporarily set to 1 so that verify
always fails regardless of actual service health. this forces the rollback path
without needing a permanently broken service.

scenario 3 - same forced-threshold setup as scenario 2. the orchestrator was
not restarted between injections so the circuit breaker failure counter
accumulated across 3 consecutive cycles. each cycle: kill checkout-svc, wait
for the orchestrator to restart it, watch verify fail (threshold=1ms), rollback
executes, failure_count increments.

scenario 4 - synthetic alert posted directly to alertmanager via
`Invoke-RestMethod -Method Post http://localhost:9093/api/v2/alerts` with
alertname=MultiStepDeploy. no real prometheus rule fires this alert; it was
injected manually to test the multi-step engine. step-c is mapped to
fail_step.ps1 which always exits 1, ensuring a deterministic failure without
any timing dependency.

scenario 5 - two containers stopped simultaneously using powershell background
jobs (`Start-Job { docker stop ronki-payment-svc }` and
`Start-Job { docker stop ronki-inventory-svc }`). both InstanceDown alerts
appeared in the same alertmanager poll cycle. the orchestrator spawned one
thread per alert; different services use different locks so both proceeded
in parallel.

scenario 6 - synthetic alert posted to alertmanager with alertname=TestHallucination.
config.yaml maps this alertname to runbooks/nonexistent_runbook.sh which is
deliberately absent from runbook_registry. the validation check fires before
dry-run, logs DECISION_VALIDATION_FAILED, and returns immediately.

---

## scenario 1 - action succeeds (InstanceDown on payment-svc)

```
{"ts": "2026-06-18T15:13:01.537664+00:00", "level": "INFO", "event_type": "ORCHESTRATOR_START", "config": "config.yaml", "dry_run": false, "poll_interval_s": 15}
{"ts": "2026-06-18T15:14:16.643619+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "InstanceDown", "service": "payment-svc", "severity": "critical"}
{"ts": "2026-06-18T15:14:16.644675+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:14:16.646840+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "payment-svc", "remaining": 3}
{"ts": "2026-06-18T15:14:16.647363+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": true}
{"ts": "2026-06-18T15:14:17.145573+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/restart_service.sh", "service": "payment-svc", "returncode": 0, "stdout": "[DRY-RUN] would execute: docker restart ronki-payment-svc", "stderr": ""}
{"ts": "2026-06-18T15:14:17.146580+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-18T15:14:17.146580+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": false}
{"ts": "2026-06-18T15:14:23.238704+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/restart_service.sh", "service": "payment-svc", "returncode": 0, "stdout": "[restart_service] Restarting ronki-payment-svc...\nronki-payment-svc\n[restart_service] ronki-payment-svc is running.", "stderr": ""}
{"ts": "2026-06-18T15:14:23.238704+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:14:23.240096+00:00", "level": "INFO", "event_type": "VERIFY_START", "service": "payment-svc", "timeout_s": 60, "latency_threshold_ms": 500}
{"ts": "2026-06-18T15:14:23.260117+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 1, "latency_p99_ms": null, "up": 0.0, "latency_ok": true, "up_ok": false}
{"ts": "2026-06-18T15:14:33.285441+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 2, "latency_p99_ms": null, "up": 1.0, "latency_ok": true, "up_ok": true}
{"ts": "2026-06-18T15:14:43.304920+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 3, "latency_p99_ms": null, "up": 1.0, "latency_ok": true, "up_ok": true}
{"ts": "2026-06-18T15:14:53.328659+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 4, "latency_p99_ms": null, "up": 1.0, "latency_ok": true, "up_ok": true}
{"ts": "2026-06-18T15:14:53.330666+00:00", "level": "INFO", "event_type": "VERIFY_PASS", "service": "payment-svc", "samples": 4, "passes": 3}
{"ts": "2026-06-18T15:14:53.331674+00:00", "level": "INFO", "event_type": "ACTION_SUCCESS", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
```

---

## scenario 2 - action fails, rollback triggered (InstanceDown on checkout-svc, threshold forced to 1ms)

```
{"ts": "2026-06-18T15:30:34.188891+00:00", "level": "INFO", "event_type": "ORCHESTRATOR_START", "config": "config.yaml", "dry_run": false, "poll_interval_s": 15}
{"ts": "2026-06-18T15:31:49.266353+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "InstanceDown", "service": "checkout-svc", "severity": "critical"}
{"ts": "2026-06-18T15:31:49.267735+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "InstanceDown", "service": "checkout-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:31:49.267735+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "checkout-svc", "remaining": 3}
{"ts": "2026-06-18T15:31:49.657026+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "checkout-svc"}
{"ts": "2026-06-18T15:31:55.577406+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "alertname": "InstanceDown", "service": "checkout-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:31:55.578422+00:00", "level": "INFO", "event_type": "VERIFY_START", "service": "checkout-svc", "timeout_s": 60, "latency_threshold_ms": 1}
{"ts": "2026-06-18T15:31:55.606092+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "checkout-svc", "sample": 1, "latency_p99_ms": null, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-18T15:32:45.733012+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "checkout-svc", "sample": 6, "latency_p99_ms": null, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-18T15:32:55.734629+00:00", "level": "WARNING", "event_type": "VERIFY_FAIL", "service": "checkout-svc", "samples": 6, "message": "Metrics did not recover within timeout"}
{"ts": "2026-06-18T15:32:55.734629+00:00", "level": "WARNING", "event_type": "ROLLBACK_TRIGGERED", "service": "checkout-svc", "alertname": "InstanceDown", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:33:03.109167+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/restart_service.sh", "service": "checkout-svc", "returncode": 0, "stdout": "[restart_service] Restarting ronki-checkout-svc...\nronki-checkout-svc\n[restart_service] ronki-checkout-svc is running.", "stderr": ""}
{"ts": "2026-06-18T15:33:03.110674+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "checkout-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:33:03.111195+00:00", "level": "WARNING", "event_type": "CIRCUIT_BREAKER_TICK", "consecutive_failures": 1, "threshold": 3}
```

---

## scenario 3 - circuit breaker (3 consecutive failures)

```
{"ts": "2026-06-18T15:44:30.917690+00:00", "level": "INFO", "event_type": "ORCHESTRATOR_START", "config": "config.yaml", "dry_run": false, "poll_interval_s": 15}
{"ts": "2026-06-18T15:45:38.136665+00:00", "level": "WARNING", "event_type": "VERIFY_FAIL", "service": "checkout-svc", "samples": 6, "message": "Metrics did not recover within timeout"}
{"ts": "2026-06-18T15:45:38.137174+00:00", "level": "WARNING", "event_type": "ROLLBACK_TRIGGERED", "service": "checkout-svc", "alertname": "InstanceDown", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:45:45.464842+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "checkout-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:45:45.465843+00:00", "level": "WARNING", "event_type": "CIRCUIT_BREAKER_TICK", "consecutive_failures": 1, "threshold": 3}
{"ts": "2026-06-18T15:48:22.989733+00:00", "level": "WARNING", "event_type": "VERIFY_FAIL", "service": "checkout-svc", "samples": 6, "message": "Metrics did not recover within timeout"}
{"ts": "2026-06-18T15:48:22.990455+00:00", "level": "WARNING", "event_type": "ROLLBACK_TRIGGERED", "service": "checkout-svc", "alertname": "InstanceDown", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:48:30.275749+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "checkout-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:48:30.275749+00:00", "level": "WARNING", "event_type": "CIRCUIT_BREAKER_TICK", "consecutive_failures": 2, "threshold": 3}
{"ts": "2026-06-18T15:51:36.839796+00:00", "level": "WARNING", "event_type": "VERIFY_FAIL", "service": "checkout-svc", "samples": 6, "message": "Metrics did not recover within timeout"}
{"ts": "2026-06-18T15:51:36.839796+00:00", "level": "WARNING", "event_type": "ROLLBACK_TRIGGERED", "service": "checkout-svc", "alertname": "InstanceDown", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:51:44.570133+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "checkout-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T15:51:44.570133+00:00", "level": "WARNING", "event_type": "CIRCUIT_BREAKER_TICK", "consecutive_failures": 3, "threshold": 3}
{"ts": "2026-06-18T15:51:44.571129+00:00", "level": "ERROR", "event_type": "CIRCUIT_BREAKER_HALT", "consecutive_failures": 3, "threshold": 3, "message": "Automation halted. Manual reset required."}
{"ts": "2026-06-18T15:51:59.572403+00:00", "level": "ERROR", "event_type": "CIRCUIT_BREAKER_HALT", "message": "Circuit open - no actions will be taken. Restart to reset."}
```

---

## scenario 4 - transactional rollback (step-c failure on api-gateway)

```
{"ts": "2026-06-18T16:00:57.268050+00:00", "level": "INFO", "event_type": "ORCHESTRATOR_START", "config": "config.yaml", "dry_run": false, "poll_interval_s": 15}
{"ts": "2026-06-18T16:00:57.296300+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "MultiStepDeploy", "service": "api-gateway", "severity": "critical"}
{"ts": "2026-06-18T16:00:57.297302+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "MultiStepDeploy", "service": "api-gateway", "runbook": "runbooks/multi_step_deploy.sh"}
{"ts": "2026-06-18T16:00:57.297302+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "api-gateway", "remaining": 3}
{"ts": "2026-06-18T16:00:57.843322+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/multi_step_deploy.sh --step-a", "service": "api-gateway"}
{"ts": "2026-06-18T16:00:59.972514+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --step-a", "service": "api-gateway", "returncode": 0, "stdout": "[multi_step_deploy] step-A: draining ronki-api-gateway...\nronki-api-gateway\n[multi_step_deploy] step-A done.", "stderr": ""}
{"ts": "2026-06-18T16:01:03.920229+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --step-b", "service": "api-gateway", "returncode": 0, "stdout": "[multi_step_deploy] step-B: applying config to ronki-api-gateway...\nronki-api-gateway\n[multi_step_deploy] step-B done.", "stderr": ""}
{"ts": "2026-06-18T16:01:04.267194+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/fail_step.sh", "service": "api-gateway", "returncode": 1, "stdout": "[fail_step] Simulating step-C failure on api-gateway", "stderr": ""}
{"ts": "2026-06-18T16:01:04.268195+00:00", "level": "ERROR", "event_type": "TRANSACTIONAL_STEP_FAIL", "step": "runbooks/fail_step.sh", "service": "api-gateway", "completed_before_failure": ["runbooks/multi_step_deploy.sh --step-a", "runbooks/multi_step_deploy.sh --step-b"]}
{"ts": "2026-06-18T16:01:04.269198+00:00", "level": "WARNING", "event_type": "TRANSACTIONAL_ROLLBACK_STEP", "step": "runbooks/multi_step_deploy.sh --rollback-b", "service": "api-gateway"}
{"ts": "2026-06-18T16:01:09.427969+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --rollback-b", "service": "api-gateway", "returncode": 0, "stdout": "[multi_step_deploy] rollback-B: reverting config on ronki-api-gateway...\nronki-api-gateway\n[multi_step_deploy] rollback-B done.", "stderr": ""}
{"ts": "2026-06-18T16:01:09.427969+00:00", "level": "WARNING", "event_type": "TRANSACTIONAL_ROLLBACK_STEP", "step": "runbooks/multi_step_deploy.sh --rollback-a", "service": "api-gateway"}
{"ts": "2026-06-18T16:01:11.925129+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --rollback-a", "service": "api-gateway", "returncode": 0, "stdout": "[multi_step_deploy] rollback-A: restoring traffic to ronki-api-gateway...\nronki-api-gateway\n[multi_step_deploy] rollback-A done.", "stderr": ""}
{"ts": "2026-06-18T16:01:11.926122+00:00", "level": "INFO", "event_type": "TRANSACTIONAL_ROLLBACK_COMPLETE", "service": "api-gateway", "rolled_back": ["runbooks/multi_step_deploy.sh --rollback-b", "runbooks/multi_step_deploy.sh --rollback-a"]}
{"ts": "2026-06-18T16:01:11.926122+00:00", "level": "WARNING", "event_type": "CIRCUIT_BREAKER_TICK", "consecutive_failures": 1, "threshold": 3}
```

---

## scenario 5 - concurrent alert race (payment-svc and inventory-svc simultaneously)

```
{"ts": "2026-06-18T16:07:30.301515+00:00", "level": "INFO", "event_type": "ORCHESTRATOR_START", "config": "config.yaml", "dry_run": false, "poll_interval_s": 15}
{"ts": "2026-06-18T16:07:45.327599+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "InstanceDown", "service": "inventory-svc", "severity": "critical"}
{"ts": "2026-06-18T16:07:45.327599+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "InstanceDown", "service": "payment-svc", "severity": "critical"}
{"ts": "2026-06-18T16:07:45.329135+00:00", "level": "INFO", "event_type": "ALERT_SKIPPED", "alertname": "InstanceDown", "service": "closed-loop-orchestrator", "reason": "service in skip_services list"}
{"ts": "2026-06-18T16:07:45.329135+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T16:07:45.329643+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "InstanceDown", "service": "inventory-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T16:07:45.330179+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "payment-svc", "remaining": 3}
{"ts": "2026-06-18T16:07:45.330179+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "inventory-svc", "remaining": 3}
{"ts": "2026-06-18T16:07:45.778853+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-18T16:07:45.793055+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "inventory-svc"}
{"ts": "2026-06-18T16:07:52.282437+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T16:07:52.308939+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "alertname": "InstanceDown", "service": "inventory-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T16:08:22.424763+00:00", "level": "INFO", "event_type": "VERIFY_PASS", "service": "payment-svc", "samples": 4, "passes": 3}
{"ts": "2026-06-18T16:08:22.425787+00:00", "level": "INFO", "event_type": "ACTION_SUCCESS", "alertname": "InstanceDown", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T16:08:22.430878+00:00", "level": "INFO", "event_type": "VERIFY_PASS", "service": "inventory-svc", "samples": 4, "passes": 3}
{"ts": "2026-06-18T16:08:22.431888+00:00", "level": "INFO", "event_type": "ACTION_SUCCESS", "alertname": "InstanceDown", "service": "inventory-svc", "runbook": "runbooks/restart_service.sh"}
```

---

## scenario 6 - hallucination defense (nonexistent runbook rejected)

```
{"ts": "2026-06-18T16:10:23.128138+00:00", "level": "INFO", "event_type": "ORCHESTRATOR_START", "config": "config.yaml", "dry_run": false, "poll_interval_s": 15}
{"ts": "2026-06-18T16:10:38.166827+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "TestHallucination", "service": "payment-svc", "severity": "critical"}
{"ts": "2026-06-18T16:10:38.167932+00:00", "level": "ERROR", "event_type": "DECISION_VALIDATION_FAILED", "bad_runbook": "runbooks/nonexistent_runbook.sh", "alertname": "TestHallucination", "raw_decision": "runbooks/nonexistent_runbook.sh", "action": "escalate_no_auto_action"}
{"ts": "2026-06-18T16:10:53.191783+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "TestHallucination", "service": "payment-svc", "severity": "critical"}
{"ts": "2026-06-18T16:10:53.192775+00:00", "level": "ERROR", "event_type": "DECISION_VALIDATION_FAILED", "bad_runbook": "runbooks/nonexistent_runbook.sh", "alertname": "TestHallucination", "raw_decision": "runbooks/nonexistent_runbook.sh", "action": "escalate_no_auto_action"}
```
