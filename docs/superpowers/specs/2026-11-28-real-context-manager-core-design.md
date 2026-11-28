# Real Context Manager Core Design

## Scope

Deliver the required demonstrable core within the constrained session: ingest versioned or user-supplied conversation data, construct a budgeted context with source-linked compression and retrievable long tool outputs, call Claude from the backend, and display the sent context, answer, actual usage, latency, and estimated cost. Provide a reproducible baseline-versus-managed evaluation path using identical questions and model parameters.

Deferred and reported honestly: Vite/TypeScript migration, production multi-user isolation, full session export/usage heatmap, prompt caching, subtask isolation, and public deployment hardening.

## Architecture

FastAPI remains the sole backend and static-file server. A context service performs deterministic artifact externalization, hard-retention selection, source-linked structured summary insertion, and budget diagnostics without network access. Provider adapters implement mock and Anthropic modes; only the backend reads the API key. API orchestration exposes separate build, compress-and-answer, and evaluation operations so budget failure never triggers a model request.

The answer workflow accepts a complete conversation plus structured memory and budget, creates or updates an early-history summary through the configured provider when compression is needed or forced, constructs the final context, validates it, calls the same provider for the answer, records content-free usage metadata, and returns evidence needed by the UI. Long tool results are stored under opaque server-generated IDs and can be retrieved through the existing artifact endpoint.

## Core behavior

- Required context includes system messages, latest user request, objective, confirmed constraints and decisions, and unfinished todos.
- A structured summary includes objective, constraints, decisions, todos, tool conclusions, and source message IDs/range.
- Summary failure leaves the source messages and previous state intact and returns a visible error.
- Context building is deterministic after a summary is supplied.
- Real calls are explicit and disabled when configuration is missing.
- The UI labels estimated build counts separately from provider-reported actual request usage.
- Evaluation sends baseline and managed context through identical answer settings and stores/report results without claiming quality improvement unless supported by the run.

## Error handling and safety

Invalid payloads return structured 422 errors. Unsatisfiable budgets include required token count, required IDs, excess, and suggestions, and do not call a provider. Provider configuration, timeout, rate-limit, and response errors return structured errors without exposing keys or response bodies. Usage logs contain metadata only, never prompts, answers, or secrets.

## Verification

Tests cover provider request translation, configured/unconfigured operation, structured compression, hard retention, no-call budget failure, end-to-end answer response, artifact retrieval, and paired evaluation behavior. Existing tests must pass. The UI is manually verified with 10/40/80-turn fixtures and 8k-to-4k budgets. A real request/evaluation is run only after the user confirms its exact request count and estimated cost.
