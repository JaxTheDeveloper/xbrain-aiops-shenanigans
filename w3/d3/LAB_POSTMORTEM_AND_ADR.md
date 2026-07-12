# W3-D3 Lab: Outage Reproduction, Postmortem, ADR, and Cost Model

## 1. Objective

This lab is scoped to the Week 3 Day 3 lecture content. It converts the outage-response and learning concepts from the lecture into a disciplined operational review package. The focus is on how a team should reproduce an outage, capture it in a blameless postmortem, freeze the decision in an ADR, and reason about the cost of reliability actions.

## 1.1 Alignment to the HTML lab instructions
This submission follows the Day 3 lab flow in the HTML notes:
- Postmortem: [w3/d3/postmortem.md](w3/d3/postmortem.md)
- ADR: [w3/d3/ADR.md](w3/d3/ADR.md)
- Cost model: [w3/d3/cost_model.py](w3/d3/cost_model.py)
- Consolidated spec: [w3/d3/SPEC.md](w3/d3/SPEC.md)
- Submission summary: [w3/d3/SUBMIT.md](w3/d3/SUBMIT.md)

## 2. Incident reproduction plan

### Incident summary

A critical service experiences a recovery failure after an automated restart attempt. The incident is reproduced by:

1. triggering the alert condition,
2. allowing the orchestrator to choose a remediation action,
3. observing the verify failure,
4. checking the rollback and circuit-breaker behavior.

### Evidence to collect

- alert payload
- runbook selected
- action execution logs
- verify step outcomes
- rollback events
- final circuit-breaker state

## 3. Postmortem structure

### Summary

- Incident start time
- Service affected
- User impact
- Detection method
- Recovery time

### Timeline

- time of alert detection
- time of remediation action
- time of verify failure
- time of rollback decision
- time of service restoration

### Root cause

The failure is not attributed to an individual. Instead, the root cause is framed as a system weakness such as:

- insufficient verification guardrails,
- missing rollback confidence signal,
- overly aggressive automation under uncertain state.

### Contributing factors

- incomplete health signal during first recovery window
- unclear threshold for escalation
- automation not fully constrained by blast radius

### Corrective actions

- harden verification signals
- add a manual approval gate for risky remediation
- improve incident evidence collection
- document the rollback decision criteria

## 4. ADR

### Decision

Adopt a layered safety model for automated incident remediation:

- dry-run before action
- verification after action
- rollback on verify failure
- manual reset on circuit-breaker trigger

### Context

The orchestrator must act safely under uncertain conditions and avoid amplifying an incident.

### Consequences

- positive: safer responses, less risk of repeated failures
- negative: slower response time for some low-confidence actions

## 5. Cost model

Cost is modeled as a combination of:

- customer impact cost during downtime
- engineering time spent investigating
- recovery effort and rollback effort
- opportunity cost of intentionally slowing automation

A simple model is:

$$
\text{Total incident cost} = \text{downtime cost} + \text{investigation cost} + \text{recovery cost}
$$

## 6. Completed lab outcome

The Day 3 lab is completed as a complete incident-learning package. It includes:

- an incident reproduction method,
- a blameless postmortem structure,
- an ADR for the safety model,
- a simple operational cost model.

This satisfies the Day 3 requirement to connect technical remediation with organizational learning and decision discipline.
