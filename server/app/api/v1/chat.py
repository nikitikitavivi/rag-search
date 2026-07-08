import json
import logging
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.db import SessionLocal
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.llm import LLMService, get_llm_service
from app.services.search import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

EmbeddingDep = Annotated[EmbeddingService, Depends(get_embedding_service)]
LLMDep = Annotated[LLMService, Depends(get_llm_service)]

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


def _build_context(doc_hits: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    if not doc_hits:
        return ""
    parts.append("DOCUMENTS:")
    for idx, hit in enumerate(doc_hits, start=1):
        title = hit.get("title", "")
        content = (hit.get("content") or "")[:800]
        parts.append(f"[{idx}] {title}: \"{content}\"")
    return "\n".join(parts)


def _build_sources(doc_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for idx, hit in enumerate(doc_hits, start=1):
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
async def chat(payload: ChatRequest, emb: EmbeddingDep, llm: LLMDep) -> StreamingResponse:
    question = payload.question.strip()

    async def event_stream() -> AsyncGenerator[str, None]:
        if not llm.is_available:
            yield _sse_event("error", "LLM API key is not configured")
            return

        async with SessionLocal() as session:
            svc = SearchService(session, emb)

            try:
                doc_hits = await svc.search_documents_rrf(question, limit=20)
            except Exception:
                logger.exception("Search failed during chat")
                yield _sse_event("error", "Search failed during chat")
                return

            doc_hits = doc_hits[:5]

            if not doc_hits:
                yield _sse_event(
                    "token",
                    "I could not find any relevant information to answer that question.",
                )
                yield _sse_event("done", "")
                return

            sources = _build_sources(doc_hits)
            yield _sse_event("sources", sources)
            context = _build_context(doc_hits)
            user_prompt = f"User question: {question}\n\nContext:\n{context}"

        try:
            async for token in llm.stream_chat(SYSTEM_PROMPT, user_prompt, max_tokens=500):
                yield _sse_event("token", token)
        except Exception:
            logger.exception("LLM streaming failed")
            yield _sse_event("error", "LLM streaming failed")
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
