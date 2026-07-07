import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.db import SessionLocal
from app.services.llm import get_llm_service
from app.services.search import MIN_SCORE, SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = (
    "You are a WealthTech assistant for financial advisors. "
    "Answer the user's question using only the context provided below. "
    "Cite sources by their number in brackets, e.g. [1] [2]. "
    "If the context does not contain enough information to answer, "
    "say so clearly. Keep answers concise and professional."
)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


def _sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps({"type": event_type, "content": data})
    return f"data: {payload}\n\n"


def _build_context(
    client_hits: list[dict[str, Any]],
    doc_hits: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    idx = 0

    if client_hits:
        parts.append("CLIENTS:")
        for hit in client_hits:
            idx += 1
            name = f"{hit.get('first_name', '')} {hit.get('last_name', '')}".strip()
            desc = hit.get("description") or ""
            email = hit.get("email", "")
            parts.append(f"[{idx}] {name} <{email}> — {desc}")

    if doc_hits:
        parts.append("\nDOCUMENTS:")
        for hit in doc_hits:
            idx += 1
            title = hit.get("title", "")
            content = (hit.get("content") or "")[:800]
            parts.append(f"[{idx}] {title}: \"{content}\"")

    return "\n".join(parts)


def _build_sources(
    client_hits: list[dict[str, Any]],
    doc_hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    idx = 0

    for hit in client_hits:
        idx += 1
        sources.append({
            "num": idx,
            "type": "client",
            "id": str(hit["id"]),
            "title": f"{hit.get('first_name','')} {hit.get('last_name','')}".strip(),
            "score": float(hit.get("score", 0)),
        })

    for hit in doc_hits:
        idx += 1
        sources.append({
            "num": idx,
            "type": "document",
            "id": str(hit["document_id"]),
            "chunk_id": str(hit["id"]),
            "title": hit.get("title", ""),
            "score": float(hit.get("score", 0)),
        })

    return sources


@router.post("", summary="Chat with RAG context (SSE streaming)")
async def chat(payload: ChatRequest) -> StreamingResponse:
    question = payload.question.strip()

    async def event_stream() -> AsyncGenerator[str, None]:
        llm = get_llm_service()
        if not llm.is_available:
            yield _sse_event("error", "LLM API key is not configured")
            return

        async with SessionLocal() as session:
            svc = SearchService(session)

            try:
                client_hits, doc_hits = await asyncio.gather(
                    svc.search_clients(question, limit=3),
                    svc.search_documents_rrf(question, limit=20),
                )
            except Exception as exc:
                logger.exception("Search failed during chat")
                yield _sse_event("error", f"Search failed: {exc}")
                return

            doc_hits = [h for h in doc_hits if h["score"] >= MIN_SCORE]
            doc_hits = doc_hits[:5]

            sources = _build_sources(client_hits, doc_hits)
            yield _sse_event("sources", sources)

            if not client_hits and not doc_hits:
                yield _sse_event(
                    "token",
                    "I could not find any relevant information to answer that question.",
                )
                yield _sse_event("done", "")
                return

            context = _build_context(client_hits, doc_hits)
            user_prompt = f"User question: {question}\n\nContext:\n{context}"

        try:
            async for token in llm.stream_chat(SYSTEM_PROMPT, user_prompt, max_tokens=500):
                yield _sse_event("token", token)
        except Exception as exc:
            logger.exception("LLM streaming failed")
            yield _sse_event("error", f"LLM streaming failed: {exc}")
            return

        yield _sse_event("done", "")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
