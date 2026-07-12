# W3-D2 Lab: Chaos Engineering and Controlled Failure Validation

## 1. Objective

This lab follows the Week 3 Day 2 lecture on chaos engineering. The purpose is to frame reliability validation as an experimental practice: deliberately inject faults into a system to uncover weaknesses before those faults appear naturally in production.

## 1.1 Alignment to the HTML lab instructions
This submission follows the Day 2 lab flow in the HTML notes:
- Experiment catalog: [w3/d2/experiments.yaml](w3/d2/experiments.yaml)
- Results scoreboard: [w3/d2/chaos_results.json](w3/d2/chaos_results.json)
- Report: [w3/d2/chaos_report.md](w3/d2/chaos_report.md)
- Submission summary: [w3/d2/SUBMIT.md](w3/d2/SUBMIT.md)

## 2. Definition from the lecture

Chaos engineering is distinct from other testing practices:

- unit tests verify code against specifications
- load tests verify behavior under expected traffic
- penetration tests focus on security weaknesses
- chaos engineering focuses on reliability weaknesses that appear through interaction and failure modes in a distributed system

## 3. Experiment design

The Day 2 lab is implemented as a controlled failure-validation plan for a reliability workflow.

### Experiment 1 — service outage

- Inject a service-down condition
- Observe whether the workflow selects the correct remediation action
- Verify the system recovers safely after the action

### Experiment 2 — failed remediation verification

- Force a verification failure after the remediation step
- Confirm that the workflow enters the rollback path instead of assuming success

### Experiment 3 — repeated failure and circuit breaker

- Reproduce repeated failed remediations
- Confirm the system halts automation after the threshold is crossed

### Experiment 4 — multi-step failure

- Introduce a partial failure in a multi-step action
- Confirm that the workflow rolls back the completed steps in order

## 4. What this lab validates

This lab validates that the reliability workflow is:

- deterministic under failure
- safe under partial success
- observable through logs and evidence
- reversible when an action does not achieve the intended effect

## 5. Why this matters

The lecture emphasizes that chaos engineering is not about breaking systems randomly. It is about learning where the system is fragile before users experience the failure. In other words, it turns reliability from a passive expectation into a testable engineering discipline.

## 6. Lab result

This Day 2 lab is completed as a structured chaos-engineering validation package. It defines the core experiments, the expected outcomes, and the operational purpose of each failure injection scenario.
