from fastapi import FastAPI, Request
from collections import deque
import json, uvicorn, statistics, time

app = FastAPI()
ALERTS_FILE   = "alerts.jsonl"
WINDOW        = 20
Z_THRESHOLD   = 3.0
COOLDOWN_SECS = 60

windows: dict[str, deque] = {
    "memory_usage_bytes":    deque(maxlen=WINDOW),
    "jvm_gc_pause_ms_avg":   deque(maxlen=WINDOW),
    "http_requests_per_sec": deque(maxlen=WINDOW),
    "queue_depth":           deque(maxlen=WINDOW),
    "http_p99_latency_ms":   deque(maxlen=WINDOW),
    "upstream_timeout_rate": deque(maxlen=WINDOW),
    "http_5xx_rate":         deque(maxlen=WINDOW),
}

baseline: dict[str, tuple[float, float]] = {}  # key -> (mean, stdev)
last_alert: dict[str, float] = {}
tick_count = 0


def fmt(v) -> str:
    return f"{v:.2f}" if v is not None else "N/A"


def z_score(key: str, value: float) -> float | None:
    if key in baseline:
        mean, stdev = baseline[key]
    else:
        w = windows[key]
        if len(w) < WINDOW:
            return None
        mean  = statistics.mean(w)
        stdev = statistics.stdev(w)
    if stdev < 1e-9:
        return None
    return (value - mean) / stdev


def maybe_freeze_baseline():
    if baseline:
        return
    if all(len(w) >= 15 for w in windows.values()):
        rps_vals   = list(windows["http_requests_per_sec"])
        queue_vals = list(windows["queue_depth"])
        if statistics.mean(rps_vals) < 300 and statistics.mean(queue_vals) < 50:
            for key, w in windows.items():
                baseline[key] = (statistics.mean(w), max(statistics.stdev(w), 1.0))
            print(f"baseline frozen at tick {tick_count}")


def fire_alert(timestamp: str, fault_type: str, severity: str, message: str):
    now = time.time()
    if now - last_alert.get(fault_type, 0) < COOLDOWN_SECS:
        return
    last_alert[fault_type] = now
    alert = {"timestamp": timestamp, "type": fault_type, "severity": severity, "message": message}
    with open(ALERTS_FILE, "a") as f:
        f.write(json.dumps(alert) + "\n")
    print(f"alert {fault_type} | {severity} | {message}")


def count_log_signals(logs: list, fault_hint: str) -> int:
    keywords = {
        "memory_leak":        ["GC pause", "OutOfMemoryWarning", "heap usage"],
        "traffic_spike":      ["Queue depth high", "server overloaded"],
        "dependency_timeout": ["Upstream timeout", "Circuit breaker"],
    }
    return sum(
        1 for log in logs
        if log.get("level") in ("WARN", "ERROR", "FATAL")
        for kw in keywords.get(fault_hint, [])
        if kw.lower() in log.get("message", "").lower()
    )


@app.post("/ingest")
async def ingest(request: Request):
    global tick_count
    tick_count += 1
    payload = await request.json()
    m    = payload["metrics"]
    logs = payload["logs"]
    ts   = payload["timestamp"]

    for key in windows:
        if key in m:
            windows[key].append(m[key])

    maybe_freeze_baseline()

    z_mem    = z_score("memory_usage_bytes", m["memory_usage_bytes"])
    z_gc     = z_score("jvm_gc_pause_ms_avg", m["jvm_gc_pause_ms_avg"])
    mem_util = m["memory_usage_bytes"] / m["memory_limit_bytes"]
    log_mem  = count_log_signals(logs, "memory_leak")
    if (z_mem is not None and z_mem > Z_THRESHOLD) or mem_util > 0.80:
        score = (z_mem or 0) + (z_gc or 0) + log_mem * 2
        if score > 2 or log_mem > 0:
            sev = "critical" if mem_util > 0.85 or (z_gc and z_gc > Z_THRESHOLD) else "warning"
            fire_alert(ts, "memory_leak", sev,
                f"mem={mem_util*100:.0f}% gc={m['jvm_gc_pause_ms_avg']}ms z_gc={fmt(z_gc)}")

    z_rps   = z_score("http_requests_per_sec", m["http_requests_per_sec"])
    z_queue = z_score("queue_depth", m["queue_depth"])
    z_lat   = z_score("http_p99_latency_ms", m["http_p99_latency_ms"])
    log_ts  = count_log_signals(logs, "traffic_spike")
    abs_spike     = (m["http_requests_per_sec"] > 400 and m["queue_depth"] > 30) or \
                    (m["http_p99_latency_ms"] > 800 and m["queue_depth"] > 30)
    spike_signals = sum(1 for z in [z_rps, z_queue, z_lat] if z is not None and z > Z_THRESHOLD)
    if tick_count % 5 == 0:
        print(f"t={tick_count} rps={m['http_requests_per_sec']:.0f} z_rps={fmt(z_rps)} "
              f"queue={m['queue_depth']} z_q={fmt(z_queue)} p99={m['http_p99_latency_ms']} "
              f"signals={spike_signals} abs={abs_spike} frozen={bool(baseline)}")
    if spike_signals >= 2 or (spike_signals >= 1 and log_ts > 0) or abs_spike:
        sev = "critical" if m["http_requests_per_sec"] > 500 or m["queue_depth"] > 100 else "warning"
        fire_alert(ts, "traffic_spike", sev,
            f"rps={m['http_requests_per_sec']:.0f} z={fmt(z_rps)} queue={m['queue_depth']} p99={m['http_p99_latency_ms']}ms")

    z_up   = z_score("upstream_timeout_rate", m["upstream_timeout_rate"])
    z_5xx  = z_score("http_5xx_rate", m["http_5xx_rate"])
    log_dt = count_log_signals(logs, "dependency_timeout")
    dt_signals = sum(1 for z in [z_up, z_5xx] if z is not None and z > Z_THRESHOLD)
    if dt_signals >= 1 and (m["upstream_timeout_rate"] > 5 or log_dt > 0):
        sev = "critical" if m["upstream_timeout_rate"] > 20 else "warning"
        fire_alert(ts, "dependency_timeout", sev,
            f"upstream={m['upstream_timeout_rate']}% z={fmt(z_up)} 5xx={m['http_5xx_rate']}%")

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
