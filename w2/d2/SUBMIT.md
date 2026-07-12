1. Top-1 confidence for the largest cluster c-000-000 is 0.78. If I had to set an auto-rollback threshold, I would choose 0.85 or higher because this pipeline is based on graph traversal and text similarity, not direct causal metric evidence.

2. The classifier variant chosen is the TF-IDF similarity retrieval bonus path. It performed by matching cluster service composition and fingerprint text to historical incident summaries, then using the top historical incident class and actions as the root cause classification.

3. This pipeline is closest to a retrieval-augmented graph RCA product: it is similar to systems that use service topology plus incident history for fast triage, rather than full causal learning or LLM-only reasoning.