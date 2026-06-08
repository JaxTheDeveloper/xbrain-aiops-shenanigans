# SUBMIT - W2-D1 Alert Correlation

## Design choices

**gap_sec = 120**

All 20 alerts in the dataset fire within a 6.5-minute window (09:42:01 to 09:48:30).
The largest gap between any two consecutive alerts in this set is about 68 seconds
(between a-0019 and a-0020). A gap_sec of 120 keeps the entire incident in one session,
which is intentional. I want topology to do the separation work, not the time window.
Splitting the session too aggressively (e.g., gap_sec=30) would fragment the main
payment-svc incident into several disconnected groups, which makes the output harder
to act on and misses the causal chain.

**topology approach**

Instead of max_hop on the full graph, I use connected components on the subgraph
restricted to only the alerting services. This avoids chaining through non-alerting
intermediary nodes. For example, recommender-svc is 4 hops from payment-svc on the
full graph, but it has no direct edge to any other alerting service, so it becomes
its own cluster. search-svc is 1 hop from edge-lb on the real graph (edge-lb calls
into search-svc), so it correctly merges into the main incident cluster.

---

## EOD checkpoint answers

**1. Why does fingerprint exclude timestamp and value?**

Timestamp and value change on every fire. If they were included, a-0003 and a-0008
and a-0015 (all payment-svc|latency_p99_ms|crit) would produce three different
fingerprints and dedup would do nothing. You would end up with 20 separate entries
instead of 17 unique alert types. The fingerprint is meant to identify the kind of
problem, not the individual measurement instance.

**2. Duplicate vs correlated - what is the difference?**

A duplicate is the same alert type firing multiple times: a-0003, a-0008, a-0015 are
all payment-svc|latency_p99_ms|crit with identical values. They are the same problem
re-triggering. A correlated pair is two different alert types that share a common
cause: a-0003 (payment-svc latency) and a-0006 (checkout-svc downstream_payment_error_rate)
are different metrics on different services, but both are caused by the same pool
exhaustion event. Dedup handles the first case; session+topology handles the second.

**3. gap_sec = 30 vs gap_sec = 600**

gap_sec=30: The 40-second gap before a-0013 breaks the session there, so recommender-svc
would land in its own time group. Several other alerts would also split across session
boundaries, fragmenting the main incident into many small clusters. More clusters,
higher alert count per engineer. gap_sec=600: Everything from 09:42 to 09:48 (and
beyond) merges into one giant session. If two unrelated incidents happened within 10
minutes of each other they would incorrectly appear as one cluster.

**4. Does the correlator group recommender-svc into the main cluster?**

No. recommender-svc has no direct edge to any of the other alerting services in the
subgraph. Its only graph connections (catalog-svc and catalog-db) are not in the alert
set, so when I take the subgraph of alerting services only, recommender-svc is an
isolated node. It forms its own cluster (c-000-001) with 1 alert. This is the correct
behavior. The dataset label confirms the alert is an unrelated concurrent batch retrain.
The subgraph restriction is what makes this work. If I used the full graph with max_hop=2,
recommender-svc would chain through edge-lb and merge into the main cluster incorrectly.

**5. Biggest limitation of topology grouping and one fix**

The topology uses static graph edges defined in services.json. If search-svc is
connected to edge-lb in the graph, it always merges with edge-lb alerts, even when
the actual cause is completely unrelated (a slow catalog-db query that has nothing
to do with the payment-svc pool exhaustion). The correlator cannot distinguish a real
cascade from a coincidence in timing. One fix: weight edges by recent call volume and
error rate. If search-svc shows no elevated error rate on its edge-lb path during the
incident window, reduce the edge weight below the merge threshold. This makes topology
correlation dynamic rather than purely structural.
