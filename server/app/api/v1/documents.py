from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import bad_request, not_found
from app.core.cursor import InvalidCursorError
from app.core.db import get_session
from app.schemas.common import ErrorResponse
from app.schemas.document import (
    DocumentCreate,
    DocumentListItem,
    DocumentOut,
    DocumentPage,
)
from app.services.documents import ClientNotFoundError, DocumentService
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.llm import LLMService, get_llm_service

router = APIRouter(tags=["documents"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

SessionDep = Annotated[AsyncSession, Depends(get_session)]
EmbeddingDep = Annotated[EmbeddingService, Depends(get_embedding_service)]
LLMDep = Annotated[LLMService, Depends(get_llm_service)]

DOC_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


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
    emb: EmbeddingDep,
    llm: LLMDep,
) -> DocumentOut:
    svc = DocumentService(db, emb, llm)
    try:
        document = await svc.create(client_id, payload)
    except ClientNotFoundError as err:
        raise not_found("CLIENT_NOT_FOUND", "Client not found", resource_id=str(client_id)) from err
    return DocumentOut.model_validate(document)


@router.get(
    "/documents",
    response_model=DocumentPage,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List documents (cursor pagination)",
)
async def list_documents(
    db: SessionDep,
    emb: EmbeddingDep,
    llm: LLMDep,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Page size"),
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
) -> DocumentPage:
    svc = DocumentService(db, emb, llm)
    try:
        rows, next_cursor, has_more = await svc.list(limit, cursor)
    except InvalidCursorError as err:
        raise bad_request("INVALID_CURSOR", str(err)) from err

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
async def get_document(
    document_id: UUID,
    db: SessionDep,
    emb: EmbeddingDep,
    llm: LLMDep,
) -> DocumentOut:
    svc = DocumentService(db, emb, llm)
    document = await svc.get_by_id(document_id)
    if document is None:
        raise not_found("DOCUMENT_NOT_FOUND", "Document not found", resource_id=str(document_id))
    return DocumentOut.model_validate(document)
