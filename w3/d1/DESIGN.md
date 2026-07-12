# W3-D1 Design Notes

## 1. SLI choice for frontend
Frontend was modeled with a user-visible availability SLI rather than CPU or memory usage because the lecture explicitly treats SLIs as measures of user pain. The RUM signal is closer to the end-user experience than infrastructure saturation metrics. Three alternatives were rejected: page-load time alone is noisy and can misclassify healthy pages with slow but still acceptable performance, JavaScript error rate is too sparse, and network error rate captures only one transport path. The chosen availability SLI is therefore the most direct and least ambiguous signal for a storefront.

## 2. SLO target for api
The API SLO was set to 99.9% because the lecture frames each additional nines as a step change in operational maturity and cost. Baseline data shows the API service is already near 98.9% p99 success, which is below a conservative 99.9% target for a customer-facing path. A 99% target would be too loose for an e-commerce checkout experience, while 99.99% would imply a much higher cost envelope and stronger resilience controls than the current stack supports.

## 3. Latency threshold for the p99 slice
The latency threshold was set to 500 ms for the frontend and API paths because the lecture recommends a user-facing percentile and this threshold is a practical boundary for interactive systems. A threshold of 200 ms is too strict for a general web experience, while 1 s would be too permissive and would let obvious degradation slip through. The 500 ms cut is therefore a balanced design point that keeps the signal responsive without overfitting to a single slow request.

## 4. Reason for excluding 4xx errors
The design excludes client-side 4xx errors from the error budget except for 429, following the lecture’s guidance that user input problems should not consume the system’s reliability budget. In the sample data, a significant fraction of 4xx responses come from bad requests rather than server dysfunction. Counting them would make the SLO look worse than the actual service health, which would distort alerting and burn-rate decisions.

## 5. MWMBR tuning
The alert rules use the Google SRE-style fast/slow burn thresholds rather than a single-window threshold because the lecture emphasizes that multi-window, multi-burn-rate alerts reduce alert noise while preserving fast escalation. The chosen values are slightly conservative for the synthetic replay data: they preserve a low false-negative rate while still reducing noise compared with a static error-rate threshold. The validation report shows that this policy keeps the false-positive rate under control while still detecting the real incident window.
