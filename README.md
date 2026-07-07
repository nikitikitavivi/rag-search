# RAG Search API

WealthTech search API across clients and documents. Built with FastAPI, Postgres + pgvector, OpenAI embeddings, and LLM enrichment.

## Features

- **Client CRUD** — create, list, get clients (by id or email lookup)
- **Document CRUD** — create documents for a client, auto-chunked, enriched, and embedded on ingest
- **Hybrid search** — weighted FTS for clients + RRF-fused vector/lexical search across document chunks
- **AI chat** — streaming RAG chat endpoint with cited sources
- **Swagger docs** — auto-generated at `/docs`

## Quickstart

### Prerequisites

- Docker + Docker Compose (or Colima)
- Python 3.11+ (for local test runs)

### Run with Docker Compose

```bash
# 1. Copy env and add your OpenAI keys
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
cd server && pip install -e ".[dev]"

# 3. Run tests
python -m pytest tests/ -v
```

## API Endpoints

| Method | Path | Purpose | Error codes |
|---|---|---|---|
| `POST` | `/v1/clients` | Create a client | 422, 409 |
| `GET` | `/v1/clients` | List clients (cursor pagination) | — |
| `GET` | `/v1/clients/:id` | Get a client | 404 |
| `GET` | `/v1/clients/lookup?email=` | Look up client by email | 404 |
| `POST` | `/v1/clients/:id/documents` | Create a document (chunk, enrich, embed) | 404, 422, 503 |
| `GET` | `/v1/documents` | List documents (cursor pagination) | — |
| `GET` | `/v1/documents/:id` | Get a document | 404 |
| `GET` | `/v1/search?q=&type=` | Hybrid search (FTS + RRF fusion), optional `type=clients|documents` filter | 400 |
| `POST` | `/v1/chat` | Streaming RAG chat (SSE) | — |
| `GET` | `/health` | Health check | — |

> `/v1/search` accepts an optional `type` parameter to filter results to only clients or documents. When omitted, results are grouped by type (clients first, then documents); scores are not comparable across types.

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
  "created_at": "2026-07-06T19:00:00Z"
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
      "created_at": "2026-07-06T19:00:00Z"
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

### Search across clients and documents

```bash
curl "http://localhost:8000/v1/search?q=wealth+management"
```

## Architecture

- **FastAPI** (async) + **SQLAlchemy 2.0 async** + **asyncpg**
- **Postgres 18 + pgvector** — one DB for relational data, vectors, and FTS
- **Embeddings**: `text-embedding-3-small` (OpenAI API, 1536-dim)
- **LLM**: `gpt-4.1-nano` (OpenAI, enrichment + RAG chat)
- **Client search**: weighted generated `tsvector` column + GIN index + `websearch_to_tsquery` + `ts_rank`
- **Document search**: vector cosine similarity + lexical `ts_rank`, fused via Reciprocal Rank Fusion (RRF)
- **Migrations**: Alembic

See `ARCHITECTURE.md` for the full design document.

## Trade-offs

**Document ingest is synchronous and expensive.** Creating a document triggers chunking, LLM enrichment (document context + per-chunk hypothetical questions), and embedding — all inside the request/response cycle within a single DB transaction. A document at the max 1,000,000-char limit produces ~1,000 chunks, each making sequential LLM and embedding API calls. With no authentication, this is a cost and DoS vector: anyone can burn OpenAI credits and hold a DB connection for minutes.

Future mitigations (not implemented):
- Lower the max content size to a smaller practical ceiling.
- Batch embeddings (OpenAI accepts up to 2048 inputs per request).
- Offload enrichment to a background task and return 201 with an `indexing` status immediately.
- Add authentication so only trusted callers can trigger ingestion.

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

73 tests covering golden flows, edge cases, and service-level behaviour:

- **Golden tests** (`test_golden.py`): end-to-end flows — client search by email (TASK.md example), document creation + chunking, error coverage (404/409/422/400), FTS ranking weights
- **CRUD tests** (`test_clients.py`, `test_documents.py`): client CRUD, document CRUD with pagination
- **Search tests** (`test_search.py`, `test_search_service.py`): hybrid search across clients + documents, RRF fusion, score ordering, empty/bad queries
- **Service-level tests** (`test_embeddings.py`, `test_llm.py`): embedding generation, LLM enrichment (context + questions), streaming chat
- Embedding and LLM services are mocked in tests (no API keys needed)

```bash
cd server && python -m pytest tests/ -v
```
# rag-search
