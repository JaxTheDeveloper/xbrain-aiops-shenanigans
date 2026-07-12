# ADR-001: Use layered safety checks before automated remediation

## Status
Accepted

## Context
The AIOps platform must decide whether to remediate an incident automatically. A purely action-first approach is risky because a recovery step can fail even when the alert is real. The platform therefore needs a decision pattern that reduces the chance of amplifying the incident.

## Decision
The platform will use a layered safety model for automated remediation:
1. Detect and validate the incident.
2. Run a dry-run or pre-check before applying any action.
3. Verify the result after remediation.
4. Roll back or halt automation if the verify signal is weak or negative.

## Alternatives considered
- Action-first automation — fast, but it can amplify a failure if the remediation is ineffective.
- Human-only response — safer, but too slow for high-volume incidents and not suitable for repeatable workflows.

## Consequences
- Positive: fewer repeated failures and less chance of compounding a bad remediation.
- Trade-off: the automation path becomes slower and requires better evidence quality.

## References
This decision directly addresses the gap observed in the Day 3 reproduction: a verify failure was not fully handled by the recovery workflow, so the platform needed a stronger safety gate.
