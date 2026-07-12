# W2/D3 Execution Plan

## Goal
Build the D3 service serving assignment in `w2/d3/` using FastAPI and the D1/D2 pipeline logic.

## Deliverables
- `w2/d3/serve.py`
- `w2/d3/DESIGN.md`
- `w2/d3/SUBMIT.md`
- Optional bonus: `requirements.txt`, `Makefile`, `Dockerfile`

## Key requirements
- Use FastAPI as the production-style HTTP API.
- Define Pydantic request/response schemas.
- Implement `/healthz` and `/readyz`.
- Add latency middleware and structured logging.
- Reuse `correlate` from `w2/d1` and `run_rca` from `w2/d2` to make the endpoint end-to-end.
- Handle invalid input with 422 rather than 500.
- Keep the app runnable on a weak machine with `uvicorn serve:app --port 8000 --workers 1`.
- Write a `DESIGN.md` with architecture, latency budget, a production concern, and a FastAPI trade-off.

## Execution steps
1. Create `w2/d3/serve.py` with:
   - `FastAPI()` app instance.
   - Pydantic models: `Alert`, `IncidentRequest`, `IncidentResponse`, `ClusterOutput`, `RootCauseOutput`, `SimilarIncidentOutput`, `RecommendedActionOutput`.
   - `GET /healthz` returning `{"status": "ok"}`.
   - `GET /readyz` checking readiness conditions.
   - `POST /incident` accepting alerts and returning the RCA response.
2. Implement input validation via Pydantic.
   - Ensure `alerts` is a list and required fields are enforced.
   - Raise `HTTPException(status_code=400)` if `alerts` is empty, or rely on Pydantic for schema validation.
3. Add middleware:
   - Capture request start time.
   - Add `X-Response-Time-Ms` header to each response.
   - Optionally add structured log lines for request path, status, and latency.
4. Load `services.json` and any required D2 assets at startup.
   - Use `pathlib.Path(__file__).resolve().parent` to locate files relative to the `w2/d3` folder.
   - Keep graph and incident history loading local and lightweight.
5. Wire the pipeline:
   - Import or copy the `correlate` function from `w2/d1`.
   - Import or copy the `run_rca` function from `w2/d2`.
   - Use these in the POST handler to produce clusters, root cause, recommended actions, and similar incidents.
6. Add `/readyz` logic:
   - Check service graph load state.
   - Check pipeline components are initialized.
   - Optionally validate LLM readiness or bypass it if `AIOPS_USE_LLM=false`.
7. Add feature-flag support:
   - Use `AIOPS_USE_LLM` environment variable.
   - If disabled, run graph-only RCA and avoid any expensive or external calls.
8. Add version metadata endpoints or fields:
   - Include fixed `app_version`, `graph_version`, and loaded asset timestamps in `/version` or in response metadata if desired.
9. Validate locally:
   - Run `uvicorn serve:app --port 8000 --workers 1`.
   - Test `/healthz` returns `{"status":"ok"}`.
   - Test POST `/incident` with valid alerts returns 200 and includes `clusters`, `root_cause`, `recommended_actions`.
   - Test invalid input returns 422 and does not raise 500.
10. Submission content:
   - `w2/d3/DESIGN.md`: describe endpoint architecture, latency budget, one production concern, and why FastAPI was chosen.
   - `w2/d3/SUBMIT.md`: answer the EOD checkpoint questions using real observations from local execution.

## Notes
- Keep the implementation simple and deterministic: this is a service wrapper for the existing pipeline, not a new research project.
- Prefer code reuse from D1/D2 over duplicating logic, but copy the functions if import paths are difficult.
- Optional bonus files (`requirements.txt`, `Makefile`, `Dockerfile`) are helpful if you have bandwidth, but the core task is `serve.py`, `DESIGN.md`, and `SUBMIT.md`.
- Use `AIOPS_USE_LLM=false` for local validation to avoid external API dependency and ensure the endpoint still works.

## Acceptance checklist
- [ ] `w2/d3/serve.py` exists and starts with `uvicorn serve:app --port 8000 --workers 1`.
- [ ] `GET /healthz` returns `{"status":"ok"}`.
- [ ] `POST /incident` returns valid RCA output for a real alert payload.
- [ ] Invalid or malformed input returns 422.
- [ ] `w2/d3/DESIGN.md` documents architecture decisions and production trade-offs.
- [ ] `w2/d3/SUBMIT.md` contains measured reflections from endpoint execution.
- [ ] `w2/d3/PLAN.md` is present in the D3 folder as the implementation plan.
