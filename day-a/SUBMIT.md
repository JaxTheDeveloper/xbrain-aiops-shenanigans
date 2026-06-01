# submit.md

## screenshots
* `anomalies_comparison.png`: subplots showing the raw value stream with anomalies flagged by both detectors. detector 1 (iqr) anomalies are highlighted in red, and detector 2 (advanced isolation forest) anomalies are highlighted in orange.

## tuning log
the isolation forest model was tuned across three contamination settings using the trend-aware feature set:
* c=0.01 -> precision: 1.0000, recall: 0.0676, f1: 0.1267
* c=0.02 -> precision: 0.8947, recall: 0.1210, f1: 0.2132
* c=0.05 -> precision: 0.6737, recall: 0.2278, f1: 0.3404

contamination = 0.05 was selected for the final detector because it optimized the balance by maximizing the f1-score.

## comparison table

| metric | detector 1 (iqr) | detector 2 (advanced if) |
| :--- | :--- | :--- |
| precision | 0.7692 | 0.6737 |
| recall | 0.0356 | 0.2278 |
| f1 | 0.0680 | 0.3404 |
| false alarms | 3 | 31 |

## model artifacts
* `isolation_forest.joblib`: saved trained model object file containing the optimized trend features (< 1mb).

## reflection

### data classification
the data is stationary at its baseline but heavily right-skewed and non-gaussian. the majority of values stay close to 0.0, with sudden, massive isolated anomalies spiking up to 0.8950. the acf plot indicates an immediate drop-off with no repeating wave patterns, meaning there is no periodic seasonality.

### method selection rationale
* iqr was chosen for detector 1 because standard gaussian techniques like rolling z-score are distorted by heavy skewness. iqr uses percentiles, making it robust against high-magnitude outliers.
* isolation forest was chosen for detector 2 to capture multi-variable patterns. because isolation forest treats observations independently, explicit trend features were added: lags capture short-term state memory, differences calculate velocity and acceleration spikes, and dual rolling windows provide macro and micro baseline context.

### detector performance and trade-offs
* detector 1 (iqr) achieved a precision of 0.7692 with only 3 false alarms, but suffered from a poor recall of 0.0356. it only captures the absolute largest global spikes and completely misses any subtle or contextual anomalies.
* detector 2 (advanced isolation forest) improved the balance with an f1 score of 0.3404. adding trend features allowed us to reach a recall of 0.2278 while keeping false alarms down to 31. at lower contamination levels like c=0.01, precision hits a perfect 1.0000, but misses too many sequential anomalies. c=0.05 balances this trade-off effectively.

### Production choice
To make a desicion on whether to use IQR (in terms of outliers as anomaly) or IForest, which is based on decision trees. We depend on the generated metrics: precision, recall, f1 score. Let me reiterate that recall implies true positive rate, precision implies positive predictive value, and F1 is the harmonic mean of both precision and recall. 

Mathematically, a harmonic mean promotes similar values of precision and recall and penalises instances with high recall but very low precision, and vice versa, as you should verify.

For a rogue agent tracking or security use case, the advanced isolation forest model is the best choice. missing a real anomaly (false negative) creates far greater risk than verifying an incorrect alert (false positive). monitoring velocity shifts and multi-scale moving baselines allows the model to capture structural breaches that static statistical indicators miss entirely.