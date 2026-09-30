# Architecture

> Status: **Phase 1 — Foundation.** This document grows with each phase. Sections
> describe what exists today; planned components are explicitly marked as such.

## System overview (target)

```
Client (Next.js dashboard / REST)
        │
        ▼
FastAPI  ──►  Ingestion ──► parse ► clean ► chunk ► embed ► index (Qdrant) + metadata (PostgreSQL)
        │
        └──►  Query pipeline ──► dense / BM25 / hybrid (RRF) ► rerank ► context ► prompt ► LLM
                                   │
                                   └──► citations ► evaluation ► traces ► dashboard
```

PostgreSQL is the system of record (documents, chunk metadata, prompts, experiments,
evaluation runs, traces). Qdrant stores vectors only and can be rebuilt from PostgreSQL.

## Backend layout

```
backend/
├── app/
│   ├── main.py            # application factory + lifespan (resource creation/cleanup)
│   ├── api/               # HTTP layer only: routers, dependencies, middleware, error mapping
│   │   ├── deps.py        # DI providers (settings, engine, sessions, health checks)
│   │   ├── error_handlers.py
│   │   ├── middleware.py  # request ID + request logging (pure ASGI)
│   │   ├── router.py
│   │   └── v1/            # versioned endpoints
│   ├── core/              # framework-independent: config, errors, logging, request context
│   ├── db/                # SQLAlchemy base, engine/session factory, model registry
│   ├── observability/     # health checks (Phase 1); tracing arrives in Phase 9
│   └── schemas/           # Pydantic request/response models (API boundary)
├── alembic/               # migrations (async env, reads URL from settings)
└── tests/
    ├── unit/              # no infrastructure required
    └── integration/       # real PostgreSQL + Qdrant, opt-in (`pytest -m integration`)
```

Planned packages (`ingestion/`, `retrieval/`, `generation/`, `evaluation/`,
`experiments/`, `providers/`, `repositories/`, `domain/`) are created in the phase that
first needs them rather than as empty placeholders.

**Dependency rule:** `api` → `services/domain` → `core`. `core` and domain logic never
import FastAPI. Infrastructure objects are created once in the lifespan, stored on
`app.state` and handed to endpoints through `Depends` providers, so every one of them
can be replaced in tests with `app.dependency_overrides`.

## Request lifecycle (Phase 1)

1. `RequestContextMiddleware` accepts a safe client `X-Request-ID`
   (`[A-Za-z0-9._-]{1,128}`) or generates one, stores it in a context variable and on
   `request.state`, and echoes it in the response header.
2. The router dispatches to the endpoint; dependencies resolve settings/sessions/checks.
3. Exceptions are converted to a single error envelope by `error_handlers.py`.
4. The middleware logs one structured `request completed` line with method, path,
   status and duration.

## Error model

Every error response has the same shape:

```json
{"error": {"code": "DATABASE_UNAVAILABLE", "message": "The database is currently unavailable.", "request_id": "3f2c..."}}
```

| Source                                   | Status | Code                    |
|------------------------------------------|--------|-------------------------|
| `AppError` subclasses (domain/services)  | per class | per class (`NOT_FOUND`, `INVALID_REQUEST`, ...) |
| Request validation                       | 422    | `VALIDATION_ERROR` (input values are not echoed) |
| Framework HTTP errors (404/405/...)      | as raised | `NOT_FOUND`, `METHOD_NOT_ALLOWED`, ... |
| DB connection failures                   | 503    | `DATABASE_UNAVAILABLE`  |
| Anything else                            | 500    | `INTERNAL_ERROR` (details logged, never returned) |

Database connection failures surface inconsistently from the driver (refused/DNS
errors are raw `OSError`s that SQLAlchemy does not wrap; authentication errors become
`DBAPIError`). A `do_connect` engine hook translates *connection establishment*
failures into `DatabaseUnavailableError`, so query errors are never misclassified as
outages. This was found by an integration test, not assumed.

## Health model

| Endpoint                   | Purpose | Checks |
|----------------------------|---------|--------|
| `GET /api/v1/health/live`  | Liveness: the process is serving requests | none |
| `GET /api/v1/health/ready` | Readiness: dependencies are reachable (200 / 503) | PostgreSQL `SELECT 1`, Qdrant `/readyz` |

Checks implement a small `HealthCheck` protocol and run concurrently, each bounded by
`RAGOPS_HEALTH_CHECK_TIMEOUT_SECONDS`. Clients only see the failure *type*; driver
messages (which may contain hostnames) go to logs. The API starts even when a
dependency is down so readiness can report what is wrong. Ollama is intentionally not a
readiness dependency yet: it is added with the LLM provider in Phase 6.

## Key decisions (Phase 1)

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Async SQLAlchemy 2 + asyncpg | Non-blocking I/O in the request path; one engine per process | Async ORM rules (no lazy loading) must be respected |
| Alembic reads the URL from settings, with a `-x db_url=` override | No credentials in `alembic.ini`; tests can target a separate DB | — |
| Baseline empty revision `0001` | Version tracking exists before the first table; later changes are reviewable diffs | One no-op migration |
| Migrations run in the container entrypoint (`RAGOPS_RUN_MIGRATIONS`) | Minimal-setup local start | With multiple replicas, run migrations as a separate job instead (flag disables it) |
| stdlib `logging` + custom JSON formatter | No extra dependency; request ID on every line | Less ergonomic than structlog |
| `SecretStr` for DB URL / API keys | Secrets never appear in `repr()` or dumps | `.get_secret_value()` needed at use sites |
| Pure ASGI middleware (not `BaseHTTPMiddleware`) | Does not buffer streaming responses (needed later for token streaming) | Slightly more code |
| Integration tests opt-in and *fail* (not skip) when services are missing | A green integration run always means infrastructure was exercised | Requires `docker compose up` first |
| Non-default host ports (Postgres 5442, API 8010) | Avoid clashing with services commonly already on 5432/8000 | Configurable in `.env` |
| Python 3.12 in Docker; code targets 3.11+ | Broad wheel availability for the ML stack added later | Local dev may use a newer interpreter |
