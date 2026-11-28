# Real Context Manager Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an end-to-end context manager that ingests long business conversations, compresses them under budget, calls Claude, and displays auditable context and usage evidence.

**Architecture:** Keep FastAPI plus the existing static frontend. Isolate provider transport, deterministic context construction, request orchestration, and evaluation; real calls remain backend-only and explicit.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Anthropic Python SDK, pytest, browser JavaScript/CSS.

**Spec:** `docs/superpowers/specs/2026-11-28-real-context-manager-core-design.md`

## Global Constraints

- Preserve mock mode and all original fixture data.
- Do not expose or log API keys, prompts, answers, or business payloads.
- Do not call a real provider without user approval for the concrete request count and cost.
- Label estimated builder counts separately from provider-reported actual usage.
- Defer non-core migrations and optional features explicitly.

---

### Task 1: Restore the runnable baseline

**Files:**
- Modify: `backend/app/routes.py`
- Test: `backend/tests/test_provider_api.py`

**Interfaces:**
- Produces: valid `DebugRequest` and `RealAnswerRequest` request models.

- [ ] Restore the interrupted request class definitions.
- [ ] Run `uv run pytest -q` and record the remaining failures.
- [ ] Keep the fix limited to restoring existing behavior.

### Task 2: Complete the Anthropic provider adapter

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `backend/context/providers.py`
- Test: `backend/tests/test_provider.py`

**Interfaces:**
- Produces: `AnthropicProvider.answer(messages, question, max_tokens=...)` and `summarize(...) -> ProviderResult`.

- [ ] Add tests with a fake SDK client for message translation, usage, timeout/error mapping, and absence of content in telemetry.
- [ ] Add the official Anthropic SDK dependency and configuration.
- [ ] Implement the minimum adapter and make tests pass.

### Task 3: Implement source-linked compression and hard retention

**Files:**
- Modify: `backend/context/models.py`
- Modify: `backend/context/builder.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_context_builder.py`
- Test: `backend/tests/test_context_hardening.py`

**Interfaces:**
- Consumes: optional provider-generated `Message(role="summary")`.
- Produces: deterministic `ContextResult` with partitions, source IDs, omission evidence, and structured budget diagnostics.

- [ ] Add failing tests for structured memory hard retention and externally supplied source-linked summary.
- [ ] Implement synthetic required-memory messages and summary insertion without network calls.
- [ ] Add excess-token and suggestions to budget errors.
- [ ] Run focused tests.

### Task 4: Add end-to-end build-and-answer orchestration

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routes.py`
- Create: `backend/context/service.py`
- Test: `backend/tests/test_provider_api.py`

**Interfaces:**
- Produces: `POST /api/context/answer` returning context evidence, answer, usage, and compression metadata.
- Produces: `POST /api/context/compress` for explicit manual compression.

- [ ] Write endpoint tests using injected fake providers.
- [ ] Implement provider selection and configuration status.
- [ ] Implement forced/threshold compression, no-call budget failure, artifact persistence, answer call, and content-free recording.
- [ ] Run endpoint tests and full tests.

### Task 5: Expose the real workflow in the UI

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/styles.css`

**Interfaces:**
- Consumes: `/health`, `/api/context/compress`, `/api/context/answer`, `/api/artifacts/{id}`.

- [ ] Add provider/model status, question, answer, force-compress control, and call evidence panels.
- [ ] Connect buttons to the new endpoints while preserving the local build path.
- [ ] Render original versus sent messages, summary source IDs, artifacts, actual usage, latency, and estimated cost.
- [ ] Verify browser syntax and existing IDs.

### Task 6: Add minimal paired real evaluation

**Files:**
- Modify: `backend/evaluation.py`
- Modify: `backend/app/routes.py`
- Modify: `frontend/app.js`
- Test: `backend/tests/test_evaluation.py`

**Interfaces:**
- Produces: explicit paired baseline/managed evaluation with identical model settings and configurable question limit.

- [ ] Test paired runner with a fake provider and no real requests.
- [ ] Implement question limit, run metadata, responses, usage, latency, and simple fixed-rubric scoring.
- [ ] Add UI trigger and truthful partial/full labeling.

### Task 7: Verify and document delivery

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/demo-script.md`
- Modify: `docs/requirements-traceability.md`

**Interfaces:**
- Produces: reproducible startup and core acceptance instructions.

- [ ] Run the full suite and compile/static checks.
- [ ] Start the app and perform mock smoke tests for 10/40/80 turns and 8k/4k.
- [ ] Update exact status, real-mode instructions, safety boundaries, and deferred scope.
- [ ] Before any paid call, report exact model, request count, token/output caps, and estimated maximum cost for user approval.

## Self-review

All approved core requirements map to Tasks 1–7. Deferred scope is explicit. Provider signatures and endpoint responsibilities are consistent; no task requires a paid request before approval.
