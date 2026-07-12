# Week 3 End-to-End Development and Testing Plan

## 1. Scope and intent

This plan synthesizes the Week 3 lecture sequence from Days 1–3 and the two labs in this workspace:

- Day 1: service reliability, SLI/SLO/SLA, error budgets, and burn-rate alerting
- Day 2: chaos engineering and validation of an AIOps remediation pipeline
- Day 3: outage reproduction, postmortem discipline, ADRs, and operational cost modeling

The implementation goal is to produce a robust, testable reliability engineering workflow that covers both:

1. a closed-loop remediation orchestrator for alert-driven incident response
2. an ML lifecycle pipeline for drift detection, retraining, and safe model promotion

The work should be treated as an end-to-end system, not as isolated scripts. The success criteria are not only “does it run?” but “does it fail safely, recover predictably, and leave evidence for operators and reviewers?”

---

## 2. Design principles

The development work should follow these principles:

- Reliability first: every automated action must be gated by dry-run, blast-radius, validation, verification, and rollback logic.
- Safety over speed: the system should prefer explicit escalation over reckless automation.
- Observability by default: every important transition must emit structured logs and metrics.
- Blameless operations: incident handling and postmortems should focus on system weaknesses rather than individual errors.
- Incremental validation: each layer should be tested before the full loop is exercised.

---

## 3. End-to-end development phases

### Phase 1 — Define the operating model

Objective: establish the reliability targets and operational boundaries before implementation.

Actions:

1. Define service-level indicators for the target services.
   - Availability
   - Latency p99
   - Error rate
2. Define SLOs and error budgets.
   - Example: 99.9% monthly availability for critical services.
   - Derive the error budget from the SLO.
3. Define alert thresholds that correspond to business impact.
   - Fast burn-rate alerts for critical incidents.
   - Slow burn-rate alerts for gradual degradation.
4. Document the incident response policy.
   - Who may approve remediation?
   - When should automation stop and escalate?

Deliverables:

- SLO specification
- Burn-rate alert policy
- Incident response runbook

---

### Phase 2 — Implement the closed-loop remediation orchestrator

Objective: make the orchestrator deterministic, auditable, and safe under failure.

Implementation scope:

- Parse alerts from an alert source such as Alertmanager.
- Map alerts to runbooks.
- Enforce blast-radius controls.
- Perform dry-run checks.
- Validate runbook choices before execution.
- Execute remediation.
- Verify service health.
- Trigger rollback or circuit-breaker behavior on failure.

Recommended implementation structure:

- Rule-based decision engine for deterministic behavior
- Per-service locking for concurrency safety
- Transactional rollback behavior for multi-step remediation
- Structured event logging for every decision and transition
- Manual reset of the circuit breaker after repeated failures

Reference implementation points:

- [w3/lab_closed_loop/closed_loop.py](w3/lab_closed_loop/closed_loop.py)
- [w3/lab_closed_loop/DESIGN.md](w3/lab_closed_loop/DESIGN.md)

Deliverables:

- Operational orchestrator
- Guardrails for blast-radius and state safety
- Audit log of all actions and retries

---

### Phase 3 — Implement the ML lifecycle loop

Objective: create a model lifecycle that can detect drift, retrain safely, and roll back when necessary.

Implementation scope:

- Train an initial model on baseline data.
- Detect drift from incoming data.
- Retrain a candidate model.
- Hold candidate models in staging.
- Promote only after approval or a defined safety gate.
- Reload the serving API after a production swap.
- Emit audit events for rollback decisions.

Recommended implementation structure:

- Baseline training pipeline
- Drift detector with feature-based and holdout-based checks
- Candidate model registration in a model registry
- Blue-green style alias swap for production promotion
- Explicit rollback path to the previous production version

Reference implementation points:

- [w3/lab_ml_lifecycle/pipeline.py](w3/lab_ml_lifecycle/pipeline.py)
- [w3/lab_ml_lifecycle/serve.py](w3/lab_ml_lifecycle/serve.py)
- [w3/lab_ml_lifecycle/README.md](w3/lab_ml_lifecycle/README.md)
- [w3/lab_ml_lifecycle/DESIGN.md](w3/lab_ml_lifecycle/DESIGN.md)

Deliverables:

- Retraining workflow
- Drift-triggered model candidate generation
- Safe promotion and rollback path

---

### Phase 4 — Build the evidence layer

Objective: make the system inspectable and understandable during incidents.

Actions:

1. Add structured events for:
   - alert detection
   - decision selection
   - dry-run outcome
   - action execution
   - verification pass/fail
   - rollback
   - circuit-breaker state change
2. Expose metrics for:
   - action counts
   - verification status
   - active version
   - rollback counters
3. Capture runbooks and incident artifacts for review.

Deliverables:

- Event logs
- Metrics endpoint
- Incident evidence bundle

---

## 4. Testing strategy

The testing plan should be layered and explicit.

### 4.1 Unit tests

Target: isolated logic and data transformations.

Examples:

- runbook mapping logic
- blast-radius guard calculation
- circuit-breaker state transitions
- validation of registry entries
- drift threshold evaluation
- alias promotion and rollback logic

Acceptance criteria:

- each decision path is deterministic
- edge cases are covered
- no silent fallback behavior remains untested

### 4.2 Integration tests

Target: interaction across components.

Examples:

- alert detection → decision → runbook execution → verification → success/failure
- drift detector → retraining workflow → model registration → serving reload
- promotion alias update → active-version endpoint reflects the new model

Acceptance criteria:

- the full control loop completes end to end without manual intervention
- logs and metrics are emitted at each stage
- failures leave the system in a known safe state

### 4.3 Scenario-based chaos tests

Target: the exact failure patterns taught in the lecture.

Minimum scenarios:

1. instance-down recovery
2. failed verification and rollback
3. repeated failures and circuit-breaker halt
4. transactional rollback for a multi-step action
5. concurrent alert handling
6. hallucinated runbook rejection

Acceptance criteria:

- each scenario produces a distinct, explainable outcome
- the orchestrator does not corrupt state during concurrent actions
- the system degrades safely rather than unpredictably

### 4.4 Operational validation tests

Target: real-world readiness.

Examples:

- verify logs are readable by on-call engineers
- confirm the rollback path is visible in the audit trail
- confirm the service returns the correct active version after promotion
- confirm the system still functions after a manual reset

Acceptance criteria:

- a new on-call engineer can understand the incident story from the logs alone
- there is enough evidence to write a valid postmortem

---

## 5. Verification checklist

The work is complete only when all of the following are true:

- SLOs and error budgets are documented and traceable to alerts.
- The remediation logic is deterministic and safe.
- The orchestrator passes all scenario-based tests.
- The ML lifecycle drift detection and retraining path has been exercised end to end.
- Rollback works and is observable.
- The service exposes clear active-version and health information.
- The logs are sufficient to support a postmortem and ADR.

---

## 6. Recommended delivery order

1. Reliability objectives and runbook policy
2. Closed-loop orchestrator core logic
3. Unit and integration tests for orchestrator safety
4. ML drift detection and retraining workflow
5. Promotion and rollback path
6. End-to-end scenario tests
7. Postmortem and ADR artifacts

---

## 7. Expected outcome

By the end of this work, the system should demonstrate three capabilities:

1. it can detect and contain incidents automatically
2. it can learn from drift and maintain model quality over time
3. it can produce enough evidence for rigorous operational review

That is the real objective of Week 3: not just building automation, but building trustworthy automation that can be operated, audited, and improved.
