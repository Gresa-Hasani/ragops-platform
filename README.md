# RAGOps — Production RAG Evaluation & Observability Platform

RAGOps is a platform for building, evaluating, comparing and debugging
Retrieval-Augmented Generation systems. It is built around one engineering question:

> **How do we know whether a RAG system is actually good?**

Evaluation (retrieval metrics, groundedness, citation validity) and observability
(per-stage traces and latency) are first-class components, not add-ons.

## Project status

The project is built in phases. Only completed phases are described as working.

| Phase | Scope | Status |
|------:|-------|--------|
| 1 | Foundation: FastAPI, config, PostgreSQL, SQLAlchemy, Alembic, Docker Compose, health checks, error handling, tests | ✅ Done |
| 2 | Document ingestion (PDF/TXT/MD, cleaning, chunking, metadata) | Planned |
| 3 | Embeddings & dense retrieval (Sentence Transformers, Qdrant) | Planned |
| 4 | BM25, hybrid retrieval, Reciprocal Rank Fusion | Planned |
| 5 | Cross-encoder reranking | Planned |
| 6 | LLM integration (Ollama), prompts, context builder, citations | Planned |
| 7 | Evaluation (retrieval + generation metrics, groundedness) | Planned |
| 8 | Experiments & A/B comparison | Planned |
| 9 | Observability: traces and stage latency | Planned |
| 10 | Next.js dashboard | Planned |
| 11–12 | Hardening, CI/CD, final verification | Planned |

## Architecture

See [docs/architecture.md](docs/architecture.md) for the layout, request lifecycle,
error model and design decisions.

**Stack (so far):** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async, asyncpg),
Alembic, PostgreSQL 17, Qdrant, Docker Compose, pytest, ruff, mypy (strict).

## Quick start (Docker)

```bash
cp .env.example .env          # adjust passwords / host ports if needed
docker compose up -d --build
curl http://localhost:8010/api/v1/health/ready
```

- API docs (OpenAPI/Swagger): http://localhost:8010/docs
- Default host ports: API `8010`, PostgreSQL `5442`, Qdrant `6333` (change in `.env`).
- The backend container applies database migrations on start
  (disable with `RAGOPS_RUN_MIGRATIONS=false`).

## Local development (backend)

```bash
docker compose up -d postgres qdrant
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8010
```

Configuration is read from `RAGOPS_*` environment variables, the repository-root `.env`
and an optional `backend/.env` override. See [.env.example](.env.example).

## API (Phase 1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health/live` | Liveness — process is up, no dependency checks |
| GET | `/api/v1/health/ready` | Readiness — PostgreSQL and Qdrant reachable (200) or not (503) |

Every response carries an `X-Request-ID` header (a valid client-supplied value is
propagated). Errors use one envelope:

```json
{"error": {"code": "NOT_FOUND", "message": "Not Found", "request_id": "3f2c9a..."}}
```

## Testing & quality checks

```bash
cd backend
pytest                          # unit tests (no infrastructure needed)
pytest -m integration           # integration tests (needs: docker compose up -d postgres qdrant)
ruff check . && ruff format --check .
mypy
```

Integration tests use a separate `ragops_test` database (created by
`infra/postgres/init/`) and **fail rather than skip** when services are missing.

## Ollama

The LLM provider (Phase 6) will default to Ollama running **on the host**
(`http://host.docker.internal:11434` from containers), which gives the best GPU support
on Windows/macOS. A Docker-based Ollama option will be documented in that phase.

## Repository layout

```
backend/        FastAPI service (app/, alembic/, tests/)
docs/           Architecture and design documentation
infra/          Infrastructure support files (Postgres init scripts)
docker-compose.yml
.env.example
```
