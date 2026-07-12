# Postmortem — Synthetic Outage Reproduction

## Summary
- Incident ID: SYN-001
- Service affected: checkout API
- User impact: checkout requests experienced intermittent failures and elevated latency during the injected failure window.
- Detection method: synthetic alert from the monitoring stack followed by pipeline-based correlation.
- Recovery time: approximately 8 minutes from detection to restoration.

## Impact
- Customers saw elevated checkout failures for a short period.
- The incident consumed a portion of the service error budget and increased investigation load.

## Timeline
- 2026-06-01T03:00:00Z — alert fired for the checkout path.
- 2026-06-01T03:00:25Z — incident channel opened and the runbook was selected.
- 2026-06-01T03:01:10Z — remediation action was attempted.
- 2026-06-01T03:02:20Z — verification step reported a failed recovery signal.
- 2026-06-01T03:03:05Z — rollback decision was triggered.
- 2026-06-01T03:04:00Z — the system was stabilized and synthetic probes recovered.
- 2026-06-01T03:06:30Z — the incident review started.
- 2026-06-01T03:08:00Z — mitigation was confirmed and the service returned to steady state.

## Root cause
The outage was caused by a failure mode that combined a service-side issue with incomplete verification after remediation. The system had enough evidence to detect the problem but not enough guardrails to ensure the recovery action was actually successful before the workflow moved on.

## Contributing factors
- The verification step did not provide a strong enough signal for a successful recovery.
- The automation path could proceed with incomplete confidence.
- The runbook allowed a remediation action to continue even though the initial symptom had not fully subsided.

## Detection
- The pipeline detected the incident within 25 seconds of the alert fire.
- The pipeline did not fully distinguish the initial symptom from the underlying dependency issue in one replay case.
- Two specific detection gaps were observed: a stateful storage fault and a monitoring-pipeline disk-fill case were missed.

## Resolution
- The remediation path was rolled back after the verify signal failed.
- The service recovered after the corrective action and verification loop completed.

## Corrective actions
- Add a stronger post-remediation verification gate.
- Require a manual confirmation step for high-risk actions.
- Improve detector coverage for stateful faults and meta-monitoring failures.
- Capture richer evidence for each incident step so future reviews are more precise.
