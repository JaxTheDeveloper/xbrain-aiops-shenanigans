# AIOps Mini-Platform Spec — Copilot

## 1. Platform overview
This mini-platform monitors a three-tier e-commerce stack with a frontend, an API tier, and a database tier. The platform combines SLO-based detection, correlation, RCA, chaos validation, outage reproduction, and cost analysis to support operational reliability decisions.

## 2. SLO definition (from W3-D1)
The platform uses three service entries in the SLO spec: frontend, api, and db. The selected SLIs are availability-based, with targets of 99.0% for frontend, 99.9% for API, and 99.9% for the database path. The associated error budgets and MWMBR alert rules are captured in the Day 1 YAML files.

## 3. Detection + Correlation + RCA stack (from W1+W2)
Detection relies on alerting from service-level failures, while correlation groups related signals into a single incident context. RCA then selects the likely root service based on topology, latency impact, and fault patterns. The Day 2 chaos report shows that this approach performs well on direct latency and availability issues but still has gaps in storage-pressure and retry-storm cases.

## 4. Reliability validation (from W3-D2)
The chaos exercise validates the pipeline across 10 experiments. The scoreboard records 7 detections out of 10, 5 correct RCA choices out of 7 detected, 1 false alarm in the baseline window, and an MTTD p50 of 28 seconds. The top gaps are stateful fault coverage, meta-monitoring coverage, and RCA bias in retry-storm scenarios.

## 5. Operational pattern (from W3-D3)
The Day 3 outage reproduction uses a synthetic incident with alerting, remediation, verification, rollback, and recovery. The key learning is that automated remediation needs layered safety checks. The ADR captured in this package documents that decision.

## 6. Cost model (from W3-D3)
The cost model uses the monthly value of avoided downtime multiplied by an expected MTTR reduction rate and compares it to the monthly AIOps cost. The script prints worked examples for representative deployments and shows that the investment is worthwhile only when downtime cost and incident volume are high enough.

## 7. Open risks
- State failure modes such as memory pressure and storage faults can still be missed.
- Monitoring-pipeline issues are under-covered and need explicit tests.
- RCA remains vulnerable to retry-storm bias and needs more topology-aware reasoning.
