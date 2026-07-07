import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import not_found
from app.core.cursor import decode_cursor, encode_cursor
from app.core.deps import get_db
from app.models.client import Client
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.common import ErrorResponse
from app.schemas.document import (
    DocumentCreate,
    DocumentListItem,
    DocumentOut,
    DocumentPage,
)
from app.services.embeddings import get_embedding_service
from app.services.llm import get_llm_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

SessionDep = Annotated[AsyncSession, Depends(get_db)]

DOC_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _build_enriched_text(doc_context: str, questions: list[str], chunk_content: str) -> str:
    parts: list[str] = []
    if doc_context.strip():
        parts.append(doc_context.strip())
    for q in questions:
        q = q.strip()
        if q:
            parts.append(q)
    parts.append(chunk_content)
    return "\n".join(parts)


@router.post(
    "/clients/{client_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    responses=DOC_ERRORS,
    summary="Create a document for a client (chunks, enriches, embeds, indexes)",
)
async def create_document(
    client_id: UUID,
    payload: DocumentCreate,
    db: SessionDep,
) -> Document:
    from app.models.client import Client

    client = (await db.execute(select(Client).where(Client.id == client_id))).scalar_one_or_none()
    if client is None:
        raise not_found("CLIENT_NOT_FOUND", "Client not found", resource_id=str(client_id))

    document = Document(
        client_id=client_id,
        title=payload.title,
        content=payload.content,
    )
    db.add(document)
    await db.flush()

    chunks_text = _splitter.split_text(payload.content)
    emb_service = get_embedding_service()
    llm = get_llm_service()

    doc_context = ""
    try:
        doc_context = llm.document_context(payload.title, payload.content)
    except Exception as exc:
        logger.warning("Document context generation failed: %s", exc)

    for i, chunk_text in enumerate(chunks_text):
        questions: list[str] = []
        try:
            questions = llm.hypothetical_questions(chunk_text)
        except Exception as exc:
            logger.warning("Hypothetical questions failed for chunk %d: %s", i, exc)

        enriched = _build_enriched_text(doc_context, questions, chunk_text)

        embedding: list[float] | None = None
        try:
            embedding = emb_service.embed(enriched).tolist()
        except Exception as exc:
            logger.warning("Embedding failed for chunk %d: %s", i, exc)

        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=i,
            content=chunk_text,
            enriched_content=enriched,
            search_text=f"{payload.title}\n{chunk_text}",
            embedding=embedding,
        )
        db.add(chunk)

    await db.commit()
    await db.refresh(document)
    return document


@router.get(
    "/documents",
    response_model=DocumentPage,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List documents (cursor pagination)",
)
async def list_documents(
    db: SessionDep,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Page size"),
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
) -> DocumentPage:
    stmt = (
        select(Document, Client)
        .join(Client, Client.id == Document.client_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
    )

    if cursor:
        cursor_ts, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            (Document.created_at < cursor_ts)
            | ((Document.created_at == cursor_ts) & (Document.id < cursor_id))
        )

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.all())

    has_more = len(rows) > limit
    rows = rows[:limit]

    next_cursor = None
    if has_more and rows:
        last_doc, _ = rows[-1]
        next_cursor = encode_cursor(last_doc.created_at, str(last_doc.id))

    items = [
        DocumentListItem(
            id=doc.id,
            client_id=doc.client_id,
            client_name=f"{client.first_name} {client.last_name}",
            title=doc.title,
            content=doc.content,
            created_at=doc.created_at,
        )
        for doc, client in rows
    ]

    return DocumentPage(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        count=len(items),
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentOut,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get a document by id",
)
async def get_document(document_id: UUID, db: SessionDep) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise not_found("DOCUMENT_NOT_FOUND", "Document not found", resource_id=str(document_id))
    return document
