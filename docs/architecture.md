# Architecture

## Runtime

The FastAPI application serves the static frontend and JSON API from one local process. The frontend loads versioned synthetic fixtures, posts a conversation plus a token budget to the context builder, and renders selected messages, partitions, omissions and local artifact references.

## Context pipeline

`backend/context/models.py` defines the domain values. `backend/context/tokens.py` supplies an offline approximate counter. `backend/context/builder.py::build_context` preserves required system/latest-user messages, selects recent content, adds source-linked structured summary, truncates long tool content and returns artifact payloads. This is a deterministic demonstration policy, not a production agent runtime.

## Provider and evaluation

`backend/context/providers.py::MockProvider` returns deterministic mock responses. `backend/evaluation.py` compares a simple truncation baseline with the managed context pipeline using fixed fixtures. Its mock answers and expected-term overlap do not measure semantic model quality. No external provider or token-counting service is called.

## Data and artifacts

`backend/data/` contains versioned synthetic fixtures and hashes. Runtime artifacts and usage metadata are local files under ignored runtime paths; do not commit user conversations, credentials or third-party data. Artifact IDs are validated before local retrieval.

## Debug behavior and limits

The debug endpoint exposes only three canned errors and is disabled by default (`DEBUG_ENABLED = False`). It does not mutate conversations or call a provider. The app is intended for localhost demonstration, not public deployment. Authentication, multi-user isolation, provider secrets, exact token counting, real evaluation and full session/trace export are outside the current implementation.
