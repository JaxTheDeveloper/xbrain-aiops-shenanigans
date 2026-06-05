import argparse
import json
import statistics
import time
from collections import deque

import uvicorn
from fastapi import FastAPI, Request

parser = argparse.ArgumentParser()
parser.add_argument("--detector", default="stl", choices=["stl", "zscore"])
parser.add_argument("--port", type=int, default=8001)
parser.add_argument("--season-period", type=int, default=48)
parser.add_argument("--z-threshold", type=float, default=3.0)
parser.add_argument("--residual-window", type=int, default=20)
args, _ = parser.parse_known_args()

ALERTS_FILE     = "alerts.jsonl"
DETECTOR        = args.detector
SEASON_PERIOD   = args.season_period
Z_THRESHOLD     = args.z_threshold
RESIDUAL_WINDOW = args.residual_window
COOLDOWN_SECS   = 60

print(f"detector={DETECTOR} season_period={SEASON_PERIOD} z_threshold={Z_THRESHOLD} residual_window={RESIDUAL_WINDOW}")

history: dict[str, list[float]] = {
    "http_requests_per_sec": [],
    "http_p99_latency_ms":   [],
    "queue_depth":           [],
    "upstream_timeout_rate": [],
    "http_5xx_rate":         [],
    "memory_usage_bytes":    [],
    "jvm_gc_pause_ms_avg":   [],
}

residual_windows: dict[str, deque] = {k: deque(maxlen=RESIDUAL_WINDOW) for k in history}

last_alert: dict[str, float] = {}
tick = 0
app = FastAPI()


def seasonal_mean(series: list[float], period: int, tick_idx: int) -> float:
    # S_p = (1/m) * sum of x_{p, p+T, p+2T, ...} where p = tick_idx % period
    phase = tick_idx % period
    vals = [series[i] for i in range(phase, len(series), period)]
    return statistics.mean(vals) if vals else 0.0


def trend_mean(series: list[float], window: int = 12) -> float:
    # simple trailing moving average over last `window` observations
    tail = series[-window:] if len(series) >= window else series
    return statistics.mean(tail)


def stl_residual(key: str, value: float) -> float | None:
    # requires at least one full period to have a meaningful seasonal estimate
    series = history[key]
    n = len(series)
    if n < SEASON_PERIOD:
        return None
    s = seasonal_mean(series, SEASON_PERIOD, n)
    t = trend_mean(series)
    return value - s - t


def zscore_raw(key: str, value: float) -> float | None:
    series = history[key]
    if len(series) < 10:
        return None
    w = series[-RESIDUAL_WINDOW:]
    mean  = statistics.mean(w)
    stdev = statistics.stdev(w) if len(w) >= 2 else 0
    if stdev < 1e-9:
        return None
    return (value - mean) / stdev


def anomaly_score(key: str, value: float) -> float | None:
    if DETECTOR == "stl":
        r = stl_residual(key, value)
        if r is None:
            return None
        rw = residual_windows[key]
        rw.append(r)
        if len(rw) < 5:
            return None
        mean_r = statistics.mean(rw)
        std_r  = statistics.stdev(rw)
        if std_r < 1e-9:
            return None
        # z-score of residual against recent residual distribution
        return (r - mean_r) / std_r
    return zscore_raw(key, value)


def fmt(v) -> str:
    return f"{v:.2f}" if v is not None else "N/A"


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
    global tick
    tick += 1
    payload = await request.json()
    m    = payload["metrics"]
    logs = payload["logs"]
    ts   = payload["timestamp"]

    for key in history:
        if key in m:
            history[key].append(m[key])

    scores = {key: anomaly_score(key, m[key]) for key in history if key in m}

    if tick % 20 == 0:
        print(f"t={tick} rps={m['http_requests_per_sec']:.0f} "
              f"s_rps={fmt(scores.get('http_requests_per_sec'))} "
              f"queue={m['queue_depth']} s_q={fmt(scores.get('queue_depth'))} "
              f"n={len(history['http_requests_per_sec'])}/{SEASON_PERIOD}")

    def s(key): return scores.get(key)
    def above(key): return s(key) is not None and s(key) > Z_THRESHOLD

    log_ts = count_log_signals(logs, "traffic_spike")
    spike_z = sum(1 for k in ["http_requests_per_sec", "queue_depth", "http_p99_latency_ms"] if above(k))
    abs_spike = m["http_requests_per_sec"] > 400 and m["queue_depth"] > 30
    if abs_spike or spike_z >= 2 or (spike_z >= 1 and log_ts > 0):
        sev = "critical" if m["http_requests_per_sec"] > 500 or m["queue_depth"] > 100 else "warning"
        fire_alert(ts, "traffic_spike", sev,
            f"rps={m['http_requests_per_sec']:.0f} score={fmt(s('http_requests_per_sec'))} "
            f"queue={m['queue_depth']} p99={m['http_p99_latency_ms']}ms [{DETECTOR}]")

    log_mem  = count_log_signals(logs, "memory_leak")
    mem_util = m["memory_usage_bytes"] / m["memory_limit_bytes"]
    if above("memory_usage_bytes") or mem_util > 0.80:
        score_sum = (s("memory_usage_bytes") or 0) + (s("jvm_gc_pause_ms_avg") or 0) + log_mem * 2
        if score_sum > 2 or log_mem > 0:
            sev = "critical" if mem_util > 0.85 or above("jvm_gc_pause_ms_avg") else "warning"
            fire_alert(ts, "memory_leak", sev,
                f"mem={mem_util*100:.0f}% score={fmt(s('memory_usage_bytes'))} "
                f"gc={m['jvm_gc_pause_ms_avg']}ms [{DETECTOR}]")

    log_dt = count_log_signals(logs, "dependency_timeout")
    dt_z   = sum(1 for k in ["upstream_timeout_rate", "http_5xx_rate"] if above(k))
    if dt_z >= 1 and (m["upstream_timeout_rate"] > 5 or log_dt > 0):
        sev = "critical" if m["upstream_timeout_rate"] > 20 else "warning"
        fire_alert(ts, "dependency_timeout", sev,
            f"upstream={m['upstream_timeout_rate']}% score={fmt(s('upstream_timeout_rate'))} "
            f"5xx={m['http_5xx_rate']}% [{DETECTOR}]")

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=args.port)
