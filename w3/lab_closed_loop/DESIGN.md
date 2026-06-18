# DESIGN.md — Closed-Loop Orchestrator

## 1. Decision engine: Rule-based (Option A)

I chose a rule-based engine. The mapping is explicit, auditable, and has zero external dependencies:

```
HighLatency      → restart_service.sh
HighErrorRate    → clear_cache.sh
InstanceDown     → restart_service.sh
MultiStepDeploy  → multi_step_deploy.sh
```

Trade-offs vs LLM-based:

| | Rule-based | LLM-based |
|---|---|---|
| Latency | ~0ms | 1–3s per decision |
| Reliability | 100% offline | depends on API availability |
| Explainability | deterministic | requires logging raw response |
| Flexibility | requires code change for new alert types | new runbooks via prompt |
| Hallucination risk | none | requires registry validation (scenario 6) |

For a production AIOps loop where MTTR is measured in seconds, determinism and zero external failure modes outweigh LLM flexibility. New alert types are infrequent; a code review + deploy cycle for the runbook map is acceptable.

## 2. Blast-radius configuration

```yaml
max_actions_per_minute: 3
max_restarts_per_service_per_hour: 5
```

Rationale:
- **3 actions/min**: The stack has 5 services. Limiting to 3/min ensures a cascade failure (all 5 services alert simultaneously) still has some actions throttled rather than all 5 firing at once. This gives the operator time to observe before the orchestrator overwhelms the system.
- **5 restarts/service/hr**: A healthy service should not need more than 1–2 restarts per hour under normal conditions. 5 is generous enough not to block legitimate remediation while catching runaway restart loops (e.g., a service with a permanent startup crash).

## 3. Verify step: metric, threshold, timeout

- Metric: `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="<svc>"}[1m])) * 1000` (p99 latency in ms) AND `up{job="<svc>"}` (liveness)
- Threshold: p99 latency < **500 ms** AND up == **1**
- Timeout: **60 seconds**, polling every **10 seconds**, requiring **3 consecutive healthy samples** before declaring pass

The 3-consecutive-samples requirement prevents a transient healthy reading from masking a flapping service. At 10s intervals this adds at most 20s of extra wait on top of the first healthy reading — acceptable given a 60s budget.

## 4. Circuit-breaker reset

Reset mode: **manual** — the operator must restart the orchestrator process.

Rationale: after 3 consecutive verify failures on the same service, automation has demonstrably failed to resolve the issue. Automatic reset (e.g., after 10 minutes) risks re-triggering the same failing cycle. Manual reset forces a human to inspect the audit log, understand why the runbooks did not work, and fix the root cause before re-enabling automation. This is safer for a production e-commerce platform where each failed action can cause user-facing downtime.
