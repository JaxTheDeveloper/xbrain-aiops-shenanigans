# D3 Design Notes

The D3 service wraps the earlier D1 correlation and D2 RCA logic inside a FastAPI endpoint so alerts can be processed over HTTP instead of only inside notebooks. The request enters the `/incident` handler, is validated by Pydantic, and then flows through a lightweight correlation pass followed by graph-based root-cause scoring and TF-IDF similarity matching against historical incidents.

The latency budget is intentionally simple. Input validation is cheap, the correlation step is linear in the number of alerts, and the RCA step is dominated by TF-IDF similarity over the historical incident corpus. For a small batch of alerts this is fast enough for local serving, and it keeps the implementation deterministic and easy to reason about.

A key production concern is fault tolerance. The endpoint should not fail hard when the LLM path is unavailable, so the implementation defaults to graph-only RCA behavior when the supporting data is present and avoids external dependencies. This choice keeps the service usable during partial outages and makes the health checks meaningful for load balancers.

FastAPI was chosen over Flask because it gives native request validation, automatic OpenAPI documentation, and a clean async-friendly structure for future extension. The service is still lightweight enough to run on a modest machine with a single worker.
