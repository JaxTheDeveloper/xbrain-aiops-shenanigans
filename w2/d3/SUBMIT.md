# D3 Submission Notes

## Objective
The objective of this submission was to convert the D1 alert-correlation workflow and the D2 root-cause analysis workflow into a small, deployable HTTP service that can be exercised through standard API requests.

## Implementation Summary
A FastAPI service was implemented in [w2/d3/serve.py](w2/d3/serve.py) with three endpoints:
- `/healthz` for basic liveness checks
- `/readyz` for readiness after the required data assets are loaded
- `/incident` for end-to-end incident analysis

The service reuses the D1-style correlation logic and the D2-style graph-based RCA approach, augmented with TF-IDF retrieval over historical incidents. Request validation was added through Pydantic models to ensure malformed input is handled cleanly, and latency headers were included to support basic observability. A graceful fallback path was also implemented so the service can still return useful RCA output when richer reasoning paths are unavailable.

Supporting files for local setup and execution were added in [w2/d3/requirements.txt](w2/d3/requirements.txt), [w2/d3/Makefile](w2/d3/Makefile), and [w2/d3/Dockerfile](w2/d3/Dockerfile). Automated endpoint tests were also added in [w2/d3/tests/test_serve.py](w2/d3/tests/test_serve.py).

## Verification
The implementation was verified through both automated testing and live API checks:
1. Automated tests
   - Command: `pytest -q tests/test_serve.py`
   - Result: `4 passed, 1 warning in 5.98s`
2. Live endpoint validation
   - `/healthz` returned `{"status":"ok"}`
   - `/readyz` returned a ready-state response after the required assets were loaded
   - `/incident` returned a structured RCA response containing clusters, root cause, recommended actions, and similar incidents for a valid request
   - Empty or invalid input returned `422 Unprocessable Entity` as expected

## Design Rationale
The service was designed to remain lightweight, explainable, and deterministic. Rather than relying on an external model for the core workflow, it combines topology-aware graph scoring with historical similarity matching, which makes the RCA output easier to inspect and test.

## Observations and Limitations
- The main computational cost comes from the TF-IDF similarity step over the historical incident corpus, so runtime increases with corpus size.
- The implementation is well suited to local development and small-scale deployment, while remaining straightforward to extend for more production-oriented monitoring workflows.
- The service is resilient to partial dependency issues because it can still produce useful output from the graph-based RCA path.
