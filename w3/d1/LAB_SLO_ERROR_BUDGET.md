# W3-D1 Lab: SLO, Error Budget, and Burn-Rate Alerting

## 1. Objective

This lab follows the Week 3 Day 1 lecture on service reliability. The purpose is to translate the lecture concepts of SLI, SLO, SLA, error budgets, and burn-rate alerting into a concrete operating policy for a user-facing service.

## 1.1 Alignment to the HTML lab instructions
This submission follows the Day 1 lab flow in the HTML notes:
- Baseline input: [w3/d1/baseline.json](w3/d1/baseline.json)
- SLO spec: [w3/d1/slo_spec.yaml](w3/d1/slo_spec.yaml)
- Burn-rate rules: [w3/d1/burn_rate_alerts.yaml](w3/d1/burn_rate_alerts.yaml)
- Design rationale: [w3/d1/DESIGN.md](w3/d1/DESIGN.md)
- Submission summary: [w3/d1/SUBMIT.md](w3/d1/SUBMIT.md)

## 2. Definitions from the lecture

- SLI: a user-centered metric that reflects actual customer experience
- SLO: the target level of service quality that the team commits to
- SLA: a customer-facing agreement that may carry contractual consequences
- Error budget: the tolerated failure budget implied by the SLO
- Burn rate: the rate at which the error budget is being consumed

## 3. Service example

Service: checkout API

- User-facing SLI: successful checkout requests / total checkout requests
- Latency SLI: p99 latency below 500 ms for successful requests
- Availability SLO: 99.9% monthly availability
- Latency SLO: 99.5% of requests under 500 ms over a 30-day window

## 4. Error budget calculation

For a 99.9% availability SLO, the error budget is:

$$
100\% - 99.9\% = 0.1\%
$$

If the service handles 100,000 requests per month, the monthly failure budget is:

$$
100{,}000 \times 0.001 = 100 \text{ failed requests}
$$

In time terms, for a steady service this is roughly 43.2 minutes of allowed downtime per month.

## 5. Burn-rate alert policy

The lecture emphasizes that burn-rate alerts should be tied to how quickly the team is consuming the error budget.

### Fast burn alert

- Condition: burn rate $\geq 14.4$ over 1 hour
- Purpose: escalate severe reliability loss immediately

### Slow burn alert

- Condition: burn rate $\geq 6$ over 6 hours
- Purpose: catch gradual degradation before the error budget is exhausted

## 6. Operational response policy

When the burn rate crosses the threshold, the team should:

1. page the on-call owner,
2. open an incident channel and attach the relevant metrics,
3. pause risky releases until the service stabilizes,
4. investigate the underlying cause and record the corrective action.

## 7. Lab result

This Day 1 lab is completed as a reliability operating policy. It defines the service-level goals, quantifies the error budget, and establishes burn-rate thresholds that can be used to decide when to act.
