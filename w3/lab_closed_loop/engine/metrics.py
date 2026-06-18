"""Prometheus metrics server for the orchestrator (port 9100)."""

from prometheus_client import Counter, Gauge, start_http_server

action_counter = Counter(
    "closed_loop_actions_total",
    "Total closed-loop actions",
    ["service", "runbook", "outcome"],  # outcome: success | rollback | fail | dry_run
)

circuit_breaker_gauge = Gauge(
    "closed_loop_circuit_breaker_state",
    "Circuit-breaker state per service (0=closed 1=open)",
    ["service"],
)

blast_radius_gauge = Gauge(
    "closed_loop_blast_radius_remaining",
    "Actions remaining in blast-radius window",
    ["service"],
)

mutex_gauge = Gauge(
    "closed_loop_mutex_locked",
    "Per-service mutex (0=free 1=locked)",
    ["service"],
)

verify_status_gauge = Gauge(
    "closed_loop_verify_status",
    "Last verify result (0=fail 1=pass 2=in_progress)",
    ["service", "runbook"],
)

_started = False


def start_metrics_server(port: int = 9100) -> None:
    global _started
    if _started:
        return
    start_http_server(port)
    _started = True
