# W3-D1 Submission — Copilot

## 1. What I implemented
- Wrote a Day 1 SLO specification in [w3/d1/slo_spec.yaml](w3/d1/slo_spec.yaml)
- Wrote burn-rate alert rules in [w3/d1/burn_rate_alerts.yaml](w3/d1/burn_rate_alerts.yaml)
- Recorded the rationale in [w3/d1/DESIGN.md](w3/d1/DESIGN.md)
- Generated a baseline input file in [w3/d1/baseline.json](w3/d1/baseline.json)

## 2. Key decisions
- Used frontend availability, API availability, and DB availability as the three service-level SLI entries.
- Chose a 99.0% frontend target, 99.9% API target, and 99.9% DB target to align with the lecture’s SLO ladder and the baseline data.
- Applied the Google SRE MWMBR pattern with fast-burn and slow-burn rules to reduce noise while preserving incident detection.

## 3. Things I learned
1. SLOs are more actionable than raw error rates because they tie reliability to an explicit budget.
2. Burn-rate alerts are better than single-window alerts when the goal is to avoid both noise and delayed response.
3. The most useful SLIs are those closest to user-visible behavior, not infrastructure saturation metrics.

## 4. One thing still uncertain
- The exact Prometheus metric names and label names would need to be validated against a real replay environment, but the structure and thresholds align with the lecture’s template.

## 5. One trade-off I am not fully sure about
- The frontend target of 99.0% is intentionally conservative for a synthetic lab, but a production team might choose a higher target if the business impact of frontend failures is severe.
