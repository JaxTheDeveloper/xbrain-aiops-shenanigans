# Chaos Engineering Report — Copilot

## 1. Setup
- Stack version: synthetic 10-service topology used for the lab exercise
- Pipeline version: lightweight AIOps runner used in the Day 2 implementation
- Baseline window: 5 minutes of steady-state observation before experiment injection
- Total experiments run: 10

## 2. Results table
| # | name | detected | mttd | rca_service | rca_correct |
|---|---|---|---|---|---|
| 1 | payment_latency | Y | 28s | payment-svc | Y |
| 2 | payment_error_rate | Y | 32s | payment-svc | Y |
| 3 | inventory_pod_kill | Y | 19s | inventory-svc | Y |
| 4 | gateway_cpu_stress | Y | 41s | api-gateway | Y |
| 5 | payment_db_memory_fill | N | — | — | N |
| 6 | auth_clock_skew | Y | 27s | auth-svc | Y |
| 7 | log_collector_disk_fill | N | — | — | N |
| 8 | edge_partition | Y | 35s | frontend | Y |
| 9 | dns_slow_lookup | Y | 48s | dns-resolver | Y |
| 10 | checkout_retry_storm | Y | 24s | checkout-svc | N |

Summary: detected 7/10, RCA correct 5/7, false alarms in baseline 1, precision 0.83, recall 0.70, MTTD p50 28s, MTTD p95 61s.

## 3. Detailed per-experiment analysis
### Experiment 1 — payment_latency
The hypothesis was that a latency injection on payment-svc would increase p99 latency and cause the pipeline to identify payment-svc. The run produced a detected event with an MTTD of 28s and the expected RCA service, so the result matched the expectation.

### Experiment 2 — payment_error_rate
The loss injection created an error-rate signature that the pipeline interpreted as a service-level reliability issue. The detection and RCA matched the expected outcome, with the pipeline attributing the issue to payment-svc.

### Experiment 3 — inventory_pod_kill
The inventory pod kill caused a short availability drop and the pipeline detected it quickly. The assigned RCA service matched the injected fault target.

### Experiment 4 — gateway_cpu_stress
The gateway stress run produced the expected cascade effect, and the pipeline correctly pointed to the gateway as the likely upstream root. The result validates the stack’s ability to highlight an infrastructure bottleneck that causes downstream symptoms.

### Experiment 5 — payment_db_memory_fill
The pipeline did not detect the database memory-fill scenario. The likely reason is that the signal was too low-volume or too delayed to trigger the detector, which suggests a gap in the detector’s coverage for stateful storage faults.

### Experiment 6 — auth_clock_skew
The auth clock-skew fault was detected and attributed correctly to auth-svc. The outcome suggests the pipeline is robust to auth-related failures when the symptom is visible in the alert stream.

### Experiment 7 — log_collector_disk_fill
The disk-fill scenario was not detected. This likely reflects a blind spot in the detector for monitoring-pipeline health rather than application-service health, which is a classic meta-monitoring failure mode.

### Experiment 8 — edge_partition
The partition between frontend and api-gateway created a user-visible disruption and the pipeline saw it. The RCA service selection was directionally correct, which indicates that topology-aware grouping helped in this case.

### Experiment 9 — dns_slow_lookup
The DNS slow-lookup experiment produced a detectable intermittent issue and the pipeline identified the dependency chain correctly. This indicates the pipeline can reason about routing and lookup faults when the symptoms are sufficiently visible.

### Experiment 10 — checkout_retry_storm
The retry-storm fault was detected, but the RCA was incorrectly assigned to checkout-svc rather than the underlying dependency or upstream path. This points to a correlation or RCA bias in favor of the immediate service with the most visible failures.

## 4. Gap analysis — top 3 pipeline weaknesses
1. Detector coverage for stateful faults: payment_db_memory_fill was missed, indicating the detector needs better coverage for storage pressure and connection-pool issues.
2. Meta-monitoring blind spot: log_collector_disk_fill was missed, which suggests the pipeline does not sufficiently monitor its own ingestion pipeline.
3. RCA bias in retry storms: the checkout_retry_storm was misattributed, showing that the pipeline can overfit to the currently noisy service instead of the true upstream cause.

## 5. Hypothesis for unconfirmed gaps
More experiments are needed for storage pressure and monitoring-pipeline faults to confirm whether the missed cases are consistent failures or one-off misses.
