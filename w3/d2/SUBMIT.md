# W3-D2 Submission — Copilot

## 3 things I learned about my AIOps pipeline
1. The pipeline is fairly good at catching direct latency and availability faults but less reliable for stateful and meta-monitoring issues.
2. External synthetic probes are essential to distinguish user-visible impact from internal-only metrics.
3. RCA becomes brittle in retry-storm scenarios because the symptom-heavy service can look like the root even when the upstream dependency is the real cause.

## 1 fault I expected the pipeline to catch but it missed
- Experiment: payment_db_memory_fill
- Why I expected detection: a memory pressure fault on a stateful dependency should create enough signal to surface as an availability anomaly.
- Why the pipeline missed (hypothesis): the detector did not have enough coverage for storage-pressure symptoms, so the fault stayed below the detection threshold.

## 1 trade-off in pipeline design I want to rethink
- I would revisit whether RCA should give more weight to topology and causality than to local alert volume in retry-storm scenarios.

## Scoreboard summary
- detected: 7/10
- rca_correct: 5/7
- mttd_p50: 28s
- false_alarms: 1
- verdict: pass
