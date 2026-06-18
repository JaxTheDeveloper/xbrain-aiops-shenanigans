# SUBMIT.md - Reflection: MLOps Lifecycle Lab

## Question 1: What drift threshold did you choose and why?

The threshold is 0.15. I selected it by measuring drift on the baseline split and estimating the noise floor. The no-drift baseline score was 0.04, so 0.15 is about 3.75 times that value. On drifted.csv the score is 0.67, which is clearly above the threshold. A threshold of 0.05 would likely trigger retraining on normal daily variation. A threshold of 0.50 would likely miss early drift.

## Question 2: What happens if model v2 after retraining performs worse than v1?

The current pipeline uses a manual approval gate. An engineer reviews v2 metrics before promoting the staging model to production. If v2 is already in production and underperforms, the rollback procedure swaps the production alias back to v1 and calls POST /reload on serve.py. This avoids redeploying the service and restores the prior version quickly. The implementation also logs rollback events for audit.

## Question 3: What is the difference between data drift and concept drift?

Data drift means the input feature distribution changes, while the relationship from features to labels remains stable. Concept drift means the mapping from features to labels changes. In this lab, Evidently DataDriftPreset detects data drift by comparing feature distributions. The code also uses holdout evaluation as a secondary check, but the primary drift detector is feature based.

## Question 4: Why is a blue-green swap more important than replacing the model file directly?

Replacing the model file directly can cause race conditions and makes rollback harder. With the MLflow alias swap, production changes are atomic. Serve.py reloads the new model only after the alias swap, and the previous version can be restored immediately if needed.

## Question 5: If you automated the approval gate, what metric and threshold would you use?

I would use the anomaly rate delta between v2 and v1 on a validation window. The conditions for auto-promotion would be:

- anomaly rate difference less than 0.05
- v2 anomaly rate below 0.10
- v2 anomaly rate above 0.01

These thresholds are conservative enough to avoid promoting a degenerate model while still allowing stable candidates to move forward. Additional checks should include a drift score below threshold on the validation window and alerting an engineer if the conditions are not met.
