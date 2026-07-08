# RAG Search API

WealthTech search API across clients and documents. Built with FastAPI, Postgres + pgvector, OpenAI embeddings, and LLM enrichment.

vercel demo link https://rag-search-two.vercel.app/

## Features

- **Clients** — create, list, get (by id or email lookup)
- **Documents** — create documents for a client, auto-chunked, enriched, and embedded on ingest; list and get
- **Hybrid search** — weighted FTS for clients + RRF-fused vector/lexical search across document chunks
- **AI chat** — streaming RAG chat endpoint with cited sources
- **Swagger docs** — auto-generated at `/docs`
- https://rag-search-two.vercel.app/docs (Swagger)
- https://rag-search-two.vercel.app/redoc (ReDoc)

## Design decisions

### Client search

Client search is weighted Postgres full-text search over a generated `tsvector` column with a **GIN index**. Fields are weighted so a match in the name or email (weight A) always outranks a match in the description (weight C) or social links (weight D).

Trigram/fuzzy matching (`pg_trgm`) was deliberately left out. For a client-search API, exact-word matching is the right default: advisors search by names, emails, and identifiers, and the `simple` FTS config (no stemming, no stop words) keeps things like the `neviswealth` part of an email reliably searchable.

### Document search (RAG)

Documents use **hybrid retrieval**, with the two result lists fused via **Reciprocal Rank Fusion** (k = 60):

1. **Lexical** — the same FTS approach as clients (`ts_rank` over a generated `tsvector`). Postgres has no native BM25, so this is a BM25-style stand-in. It exists because exact-term matching is valuable for things embeddings handle poorly: error codes, IDs, emails, exact names.
2. **Semantic** — OpenAI `text-embedding-3-small` (1536-dim) vectors in pgvector, searched by cosine distance with an **HNSW index**. This is what powers the "address proof" → "utility bill" case.

Search returns individual **chunks** (not the parent document) — this simulates how Rack Search surfaces relevant snippets rather than full documents.

Ingestion pipeline (on `POST /clients/{id}/documents`):

- Chunking with overlap via `langchain-text-splitters` (`RecursiveCharacterTextSplitter`, 1200 chars, 200 overlap).
- **Contextual retrieval**: `gpt-4.1-nano` generates a one-sentence document context that is prepended to every chunk.
- **Chunk enrichment**: the same model generates 2–3 hypothetical questions per chunk (questions an advisor might ask that the chunk answers).
- Only the *enriched* text (context + questions + chunk) is embedded; the lexical index uses just `title + raw chunk`, so enrichment boosts semantic recall without polluting exact-match results.

`gpt-4.1-nano` was picked as a fast/cheap model that is good enough for enrichment. Neither the LLM nor the embedding model was benchmarked against alternatives — a proper model comparison was out of scope for an MVP. OpenAI-hosted embeddings were chosen over local models to avoid local-inference setup overhead.

### Chat

`POST /v1/chat` is a small GPT-style chat over the data (SSE streaming): each question runs the same hybrid search, the top hits are passed to the LLM as numbered context, and answers cite sources as `[1]`, `[2]`.

## Quickstart

### Prerequisites

- Docker
- Python 3.11+ (for local test runs)

### Run with Docker Compose

```bash
# 1. Copy env and add your OpenAI keys
cp .env.example .env
# edit .env:
#   OPENAI_API_KEY=sk-...             (LLM: enrichment + chat)
#   OPENAI_EMBEDDINGS_API_KEY=sk-...  (embeddings: semantic search)
# Without the embeddings key, documents are stored without vectors and
# search silently degrades to lexical-only.

# 2. Start Postgres + API
docker-compose up -d

# 3. Check health
curl http://localhost:8000/health
# {"status":"ok"}

# 4. Open Swagger UI
open http://localhost:8000/docs
```

## Deployment

Deployed on **Vercel** (serverless Python function) with a free-tier hosted Postgres (**Neon**). Expect cold-start latency on the first request; it runs noticeably faster locally via `docker-compose`. Cheap infrastructure was a deliberate MVP choice.

## API Endpoints

| Method | Path | Purpose | Error codes |
|---|---|---|---|
| `POST` | `/v1/clients` | Create a client | 422, 409 |
| `GET` | `/v1/clients` | List clients (cursor pagination) | 400 |
| `GET` | `/v1/clients/:id` | Get a client | 404 |
| `GET` | `/v1/clients/lookup?email=` | Look up client by email | 404 |
| `POST` | `/v1/clients/:id/documents` | Create a document (chunk, enrich, embed) | 404, 422 |
| `GET` | `/v1/documents` | List documents (cursor pagination) | 400 |
| `GET` | `/v1/documents/:id` | Get a document | 404 |
| `GET` | `/v1/search?q=&type=` | Hybrid search (FTS + RRF fusion), optional `type=clients\|documents` filter | 400 |
| `POST` | `/v1/chat` | Streaming RAG chat (SSE) | — |
| `GET` | `/health` | Health check | — |

> `/v1/search` accepts an optional `type` parameter to filter results to only clients or documents. When omitted, results are grouped by type (clients first, then documents); scores are not comparable across types.

All handled errors return a shared `ErrorResponse` schema:
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

## Trade-offs & deliberate simplifications

**Document ingest is synchronous.** Done deliberately for simplicity — in production, ingestion could be done asynchronously. The current MVP also doesn't handle updating or re-indexing documents.

**No reranking.** Listed as a future improvement: retrieve a larger candidate set, then apply a cross-encoder reranking step. Overkill for an MVP take-home.

**No authentication or rate limiting.** All endpoints are public; acceptable for a take-home demo, not for production.

**English-focused.** The FTS `simple` config does no stemming or language-specific processing; no multilingual tuning was done.

**Graceful degradation.** Without OpenAI keys configured, documents are stored without embeddings and search falls back to lexical-only.

**Frontend is a thin demo.** Minimal time was invested there; rough edges are expected.

## Project layout

```
rag-search/
  server/                      # FastAPI backend
    app/
      main.py                  # app factory
      core/                    # config, db, cursor
      models/                  # SQLAlchemy ORM
      schemas/                 # Pydantic v2 I/O
      services/                # clients, documents, embeddings, llm, search
      api/v1/                  # route handlers
      fixtures.py              # seed data
    migrations/                # Alembic DB migrations
    scripts/                   # seed + search-quality scripts
    tests/                     # pytest + httpx
    pyproject.toml
    Dockerfile
  frontend/                    # Vite/React demo UI
  api/index.py                 # Vercel serverless entry point
  docker-compose.yml           # postgres+pgvector, api, frontend
  vercel.json                  # Vercel routing + function config
  .env.example
  ARCHITECTURE.md · TASK.md
```

## Tests

74 tests covering golden flows, edge cases, and service-level behaviour:

- **Golden tests** (`test_golden.py`): end-to-end flows — client search by email (TASK.md example), document creation + chunking, error coverage (404/409/422/400), FTS ranking weights
- **CRUD tests** (`test_clients.py`, `test_documents.py`): client create/get/list, document create/get including chunk + embedding persistence
- **Pagination tests** (`test_pagination.py`): cursor pagination on clients — page boundaries, invalid cursors, full iteration
- **Search tests** (`test_search.py`, `test_search_service.py`): hybrid search across clients + documents, RRF fusion, ranking weights, BM25 fallback when embeddings are unavailable, empty/bad queries
- **Service-level tests** (`test_embeddings.py`, `test_llm.py`): embedding generation and LLM enrichment (context + hypothetical questions), with mocked OpenAI clients

Embedding and LLM services are mocked in tests (no API keys needed). Known gaps: the `/v1/chat` SSE endpoint and document-list pagination are not yet covered.

```bash
cd server && python -m pytest tests/ -v
```
