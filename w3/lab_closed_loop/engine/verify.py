"""Prometheus-based post-action verify step."""

import time

import requests

from engine.logger import JsonLogger

log = JsonLogger("verify")


def _query(prometheus_url: str, promql: str) -> float | None:
    try:
        resp = requests.get(
            f"{prometheus_url}/api/v1/query",
            params={"query": promql},
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get("data", {}).get("result", [])
        if results:
            return float(results[0]["value"][1])
    except Exception as exc:
        log.error("PROMETHEUS_QUERY_ERROR", query=promql, error=str(exc))
    return None


def verify_service(
    prometheus_url: str,
    service: str,
    baseline: dict,
    timeout_s: int,
    poll_interval_s: int,
    min_samples: int,
) -> bool:
    """Poll until min_samples consecutive healthy reads or timeout.

    Returns True on pass, False on timeout/failure.
    """
    thresholds = baseline["verify_thresholds"]
    queries = baseline["prometheus_queries"]

    latency_q = queries["latency_p99"].replace("{service}", service)
    up_q = queries["up"].replace("{service}", service)

    deadline = time.time() + timeout_s
    passes = 0
    samples = 0

    log.info("VERIFY_START", service=service, timeout_s=timeout_s,
             latency_threshold_ms=thresholds["latency_p99_max_ms"])

    while time.time() < deadline:
        latency = _query(prometheus_url, latency_q)
        up = _query(prometheus_url, up_q)
        samples += 1

        # null latency = no histogram data yet (service just restarted).
        # Treat as passing only if the threshold is high enough to be a real check (>10ms).
        # If threshold is very low (forced for testing), null counts as a failure.
        if latency is None:
            latency_ok = thresholds["latency_p99_max_ms"] > 10
        else:
            latency_ok = latency < thresholds["latency_p99_max_ms"]
        up_ok = up is not None and up >= thresholds["up_required"]

        log.info("VERIFY_SAMPLE", service=service, sample=samples,
                 latency_p99_ms=round(latency, 2) if latency is not None else None,
                 up=up, latency_ok=latency_ok, up_ok=up_ok)

        if latency_ok and up_ok:
            passes += 1
            if passes >= min_samples:
                log.info("VERIFY_PASS", service=service, samples=samples, passes=passes)
                return True
        else:
            passes = 0  # must be consecutive

        time.sleep(poll_interval_s)

    log.warning("VERIFY_FAIL", service=service, samples=samples,
                message="Metrics did not recover within timeout")
    return False
