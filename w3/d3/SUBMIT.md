# W3-D3 Submission — Copilot

## Outage chosen
- ID: SYN-001
- Name: Synthetic checkout outage reproduction
- Why this one: It exercises the same patterns as real incident response, including alerting, remediation, verification failure, rollback, and recovery.
- Failure mode: cascading

## 3 things I learned from this outage
1. Automated remediation needs a verify step before it is considered successful.
2. Postmortems are more useful when they are blameless and focused on system design rather than individual mistakes.
3. Reliability decisions should be tied to both technical evidence and cost trade-offs.

## 1 thing my pipeline would still miss if this outage happened for real
- Pattern: stateful storage pressure and monitoring-pipeline faults
- Why miss: the detector coverage is still incomplete for these classes of failures.
- Mitigation idea: add explicit tests for storage and meta-monitoring signals.

## 1 decision in my ADR I'm not fully sure about
- The layered safety model is reasonable, but the exact threshold for when automation should pause for manual review may vary by service criticality.

## Cost model verdict for my stack
- ROI: 1.6
- Payback: 0.6 months
- Verdict: worth_it
