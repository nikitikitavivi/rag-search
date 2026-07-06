# RAG Search API

WealthTech search API across clients and documents. Built with FastAPI, Postgres + pgvector, local BGE embeddings, and OpenAI LLM summaries.

## Features

- **Client CRUD** — create, list, get clients
- **Document CRUD** — create documents for a client, auto-embedded on ingest
- **Client full-text search** — weighted `tsvector` search across name/email/description with `ts_rank` scoring
- **Document summaries** — LLM-generated summaries via `gpt-4.1-nano`, cached in Postgres
- **Swagger docs** — auto-generated at `/docs`

## Quickstart

### Prerequisites

- Docker + Docker Compose (or Colima)
- Python 3.11+ (for local test runs)

### Run with Docker Compose

```bash
# 1. Copy env and add your OpenAI key (optional — summary endpoint returns 503 without it)
cp .env.example .env
# edit .env: OPENAI_API_KEY=sk-...

# 2. Start Postgres + API
docker-compose up -d

# 3. Check health
curl http://localhost:8000/health
# {"status":"ok"}

# 4. Open Swagger UI
open http://localhost:8000/docs
```

### Run tests locally

```bash
# 1. Start just the database
docker-compose up -d db

# 2. Create a venv and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" asyncpg pydantic pydantic-settings pgvector openai alembic httpx pytest pytest-asyncio numpy email-validator

# 3. Run tests
cd server
python -m pytest tests/ -v
```

## API Endpoints

| Method | Path | Purpose | Error codes |
|---|---|---|---|
| `POST` | `/v1/clients` | Create a client | 422, 409 |
| `GET` | `/v1/clients` | List clients | — |
| `GET` | `/v1/clients/:id` | Get a client | 404 |
| `POST` | `/v1/clients/:id/documents` | Create a document (auto-embeds) | 404, 422 |
| `GET` | `/v1/documents/:id` | Get a document | 404 |
| `GET` | `/v1/documents/:id/summary` | LLM summary (cached) | 404, 503 |
| `GET` | `/v1/search?q=` | Search clients (FTS, ranked) | 400 |
| `GET` | `/health` | Health check | — |

All errors return a shared `ErrorResponse` schema:
```json
{ "detail": { "code": "CLIENT_NOT_FOUND", "message": "Client not found", "resource_id": "uuid" } }
```

## Example queries

### Create a client

```bash
curl -X POST http://localhost:8000/v1/clients \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@neviswealth.com",
    "description": "Wealth management client at NevisWealth.",
    "social_links": ["https://linkedin.com/in/johndoe"]
  }'
```

Response (201):
```json
{
  "id": "a1b2c3d4-...",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@neviswealth.com",
  "description": "Wealth management client at NevisWealth.",
  "social_links": ["https://linkedin.com/in/johndoe"],
  "created_at": "2026-07-06T19:00:00Z",
  "updated_at": "2026-07-06T19:00:00Z"
}
```

### Search clients — TASK.md example

```bash
curl "http://localhost:8000/v1/search?q=NevisWealth"
```

Response (200):
```json
[
  {
    "type": "client",
    "score": 0.06079271,
    "client": {
      "id": "a1b2c3d4-...",
      "first_name": "John",
      "last_name": "Doe",
      "email": "john.doe@neviswealth.com",
      "description": "Wealth management client at NevisWealth.",
      "social_links": ["https://linkedin.com/in/johndoe"],
      "created_at": "2026-07-06T19:00:00Z",
      "updated_at": "2026-07-06T19:00:00Z"
    }
  }
]
```

### Create a document (auto-embedded)

```bash
CLIENT_ID="a1b2c3d4-..."
curl -X POST "http://localhost:8000/v1/clients/${CLIENT_ID}/documents" \
  -H "Content-Type: application/json" \
  -d '{ "title": "Utility Bill", "content": "This utility bill serves as address proof." }'
```

### Get a document summary

```bash
DOC_ID="..."
curl "http://localhost:8000/v1/documents/${DOC_ID}/summary"
```

## Architecture

- **FastAPI** (async) + **SQLAlchemy 2.0 async** + **asyncpg**
- **Postgres 18 + pgvector** — one DB for relational data, vectors, and FTS
- **Embeddings**: `bge-base-en-v1.5` (local, in-process, 768-dim)
- **LLM**: `gpt-4.1-nano` (OpenAI, summary only, cached in DB)
- **Client search**: weighted generated `tsvector` column + GIN index + `websearch_to_tsquery` + `ts_rank`
- **Migrations**: Alembic

See `ARCHITECTURE.md` for the full design document.

## Project layout

```
rag-search/
  server/                      # FastAPI backend
    app/
      main.py                  # app factory
      core/                    # config, db, deps
      models/                  # SQLAlchemy ORM
      schemas/                 # Pydantic v2 I/O
      services/                # embeddings, llm, search
      api/v1/                  # route handlers
    tests/                     # pytest + httpx
    alembic/                   # DB migrations
    pyproject.toml
    Dockerfile
  docker-compose.yml           # postgres+pgvector, api
  .env.example
  ARCHITECTURE.md · TASK.md · IDEAS.MD
```

## Tests

31 tests covering golden flows and edge cases:

- **Golden tests** (`test_golden.py`): end-to-end flows — client search by email (TASK.md example), document creation + summary caching, error coverage (404/409/422/400), FTS ranking weights
- **Unit tests**: client CRUD, document CRUD, search variants (name/email/description/phrase/limit), summary caching + 503
- Embedding and LLM services are mocked in tests (no 440MB model download or OpenAI key needed)

```bash
cd server && python -m pytest tests/ -v
```
