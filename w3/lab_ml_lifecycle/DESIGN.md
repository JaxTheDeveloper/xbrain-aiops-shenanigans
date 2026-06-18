# DESIGN.md - MLOps Lifecycle: Anomaly Detection Pipeline

## Overview

This design document explains why this solution uses MLflow registry aliases, a manual retrain approval gate, and a sliding window training strategy. The implementation is based on the original sample-solution folder and has been extended for Windows PowerShell compatibility, more robust holdout validation, and explicit rollback and audit logging.

## Drift Threshold

Chosen threshold: 0.15. This threshold was selected by measuring drift on a baseline split and estimating the noise floor. The no-drift baseline score was 0.04, so 0.15 is about 3.75 times that value. On drifted.csv the measured score is 0.67, which is clearly above the threshold.

If the threshold is too low, the pipeline can produce false positives and trigger retraining on normal daily variation. If the threshold is too high, the pipeline can miss real drift and allow the model to serve stale data until precision and recall degrade.

## Drift Type

Detected drift type: data drift. This pipeline focuses on changes in the input feature distribution for latency_p99, error_rate, and rps.

Evidently DataDriftPreset applies statistical drift tests across features and aggregates the results into a drift score. The score is easy to interpret for feature distribution changes.

Other methods considered: Granger causation for temporal relationships and Kolmogorov-Smirnov for one-dimensional distribution comparisons. Evidently was chosen because it provides a clear drift score without adding the complexity of causal inference.

Why data drift is appropriate: in the payment gateway scenario, the production normal regime can shift. For example, if latency baseline rises from 120ms to 156ms due to a campaign and integrations, a model trained on the old baseline would misclassify normal behavior as anomalous. Detecting data drift enables retraining before production precision suffers.

The pipeline does not directly detect concept drift in production because labeled ground truth is unavailable there. Instead, the code logs performance proxies and uses holdout validation as a secondary check.

## Retrain Trigger Configuration

Trigger type: manual approval gate. The workflow is semi-automatic: drift detection can trigger candidate model training, but promotion from staging to production requires human approval.

Cadence: there is no fixed schedule. The drift detector is intended to run whenever new batch data is available, such as daily. Final production promotion is only allowed after a human review.

Why manual: anomaly detection in payments directly impacts on-call reliability. An automatically promoted, underperforming model could increase false negatives or generate an alert storm from false positives. A human approval gate ensures an ML engineer can compare key metrics before cutover.

Timeout: this lab does not implement an approval timeout. In production, a 24-hour timeout is recommended so that a staging candidate does not remain pending indefinitely. If approval is not granted within 24 hours, the candidate should be archived and the drift check cycle reset.

Fully automatic alternative: a production-ready alternative would be A/B shadow mode. This would run both production and staging models in parallel for a fixed period, compare anomaly rate drift, and auto-promote only if the candidate performs within an acceptable delta, for example less than 5% anomaly rate difference.

## Versioning and Rollback

This solution uses MLflow Registry aliases rather than hardcoded version numbers.

- production alias points to the currently active production version.
- staging alias points to the candidate retrained version.
- numeric version IDs remain as an immutable audit trail.

Why aliases: serve.py loads models:/anomaly-detector@production, so it does not need to change when a new version is promoted. Hardcoding a version number would require changing the serve configuration or redeploying.

Rollback path:
1. Detect that v2 underperforms in production.
2. Use MlflowClient.set_registered_model_alias("anomaly-detector", "archived", v2_version) and set_registered_model_alias("anomaly-detector", "production", v1_version).
3. Call POST /reload on serve.py so the service reloads the restored model.

Rollback timing: the process is designed to be fast. The alias swap and reload are lightweight and do not require redeploying the service.

Authority: in production, an ML engineer or on-call owner with MLflow admin access should manage rollback. The rollback should be captured in a runbook and logged for audit purposes.

Retention policy: older versions are retained indefinitely. The registered model artifacts are small for this IsolationForest use case, so keeping prior versions is appropriate for auditability and rollback safety.

## Architecture

```
baseline.csv (reference)
     |
     +--> pipeline.py --> MLflow run --> Registry v1 @production
     |
drifted.csv (current window)
     |
     +--> drift_detector.py
               | score=0.67 > threshold=0.15
               v
           retrain.py
               |
               +--> train IsolationForest on sliding window data
               +--> MLflow run -> Registry v2 @staging
               +--> human approval
               +--> set alias production -> v2
               +--> POST /reload -> serve.py
```

## Why combined mode is needed

Using only DataDriftPreset is not enough. Data drift detects changes in P(X), but it can miss concept drift where P(Y|X) changes while the input distribution remains stable.

For example, if a new payment processor rollout changes the anomaly definition for the same latency value, the feature distribution may appear normal even though the model is making wrong predictions. A feature-only drift score could be low while model performance degrades.

--check-mode combined uses both feature drift detection and a performance check on labeled holdout data. If the current model's precision or recall degrades on holdout.csv, the pipeline triggers retraining.

If v1 initially had 91 percent precision and then drops to 62 percent on holdout, that is a strong signal of concept drift even if the raw feature drift score remains low.

## Data selection strategy

Training v2 only on the drift window can lead to overfitting to the most recent distribution. In this lab, that means the retrained model could learn that 156ms latency is always normal and then perform poorly on the older holdout pattern.

Sliding window strategy (baseline plus drift window) is better because it exposes the model to both old and new regimes. With baseline.csv (4320 rows) plus drifted.csv (1008 rows), the combined training set is 5328 rows, which helps IsolationForest avoid being dominated by the new distribution.

Alternatives:
- pure drift window: simplest, but prone to overfitting
- weighted sampling: useful if the drift window is very small, but adds complexity
- full historical concat: safest long-term, but more expensive as data volume grows

For this lab, the sliding window is the best trade-off between stability and simplicity.

## Auto-rollback threshold and policy

After v2 is promoted to production, post_deploy_monitor evaluates precision on post_deploy_eval.csv for multiple polling cycles.

The rollback threshold is precision < 0.65. This is conservative. It is well below the baseline precision of around 0.9 but high enough to avoid rolling back due to noise in a 200-row evaluation set.

For example, if 80 rows are anomalies and the model misses 30 of them, the resulting precision is about 0.88. If the model is clearly confused, precision can fall toward 0.40. A threshold of 0.65 catches severe degradation without triggering on modest sampling variation.

Rollback flow:
- set_registered_model_alias("anomaly-detector", "archived", v2_version)
- set_registered_model_alias("anomaly-detector", "production", v1_version)
- POST /reload to refresh serve.py

The pipeline logs rollback events to outputs/audit_log.jsonl under auto_rollback_v2_to_v1, including demoted_version, restored_version, trigger_precision, and cycle.

## Observability

MLOps monitoring is different from service monitoring because the failure mode is often data drift rather than code bugs. Drift scores and precision/recall over time help detect model decay before on-call receives complaints.

The active version gauge and alias state table answer the question of which model version is actually serving traffic. The retrain event counter and auto-rollback counter provide a lightweight audit trail for system self-healing.

These metrics complement MLflow experiment tracking by making runtime and deployment state visible in the monitoring layer.

## Trade-offs

| Decision | Benefit | Cost |
|---|---|---|
| Manual approval gate | Safer, human oversight | Longer retrain loop latency |
| Data drift focus | Simpler, no production labels needed | Can miss concept drift without extra checks |
| IsolationForest | Fast training, explainable, no GPU | Does not capture temporal dependencies |
| Local artifact store | Easy setup | Not suitable for multi-node scaling |
