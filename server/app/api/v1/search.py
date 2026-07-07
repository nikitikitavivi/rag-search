from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import bad_request
from app.core.deps import get_db
from app.schemas.common import ErrorResponse
from app.schemas.search import (
    ClientResult,
    DocumentResult,
    SearchHitClient,
    SearchHitDocument,
    SearchResult,
)
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]

SEARCH_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


@router.get(
    "",
    response_model=list[SearchResult],
    responses=SEARCH_ERRORS,
    summary="Search across clients and documents (RRF-fused hybrid retrieval)",
)
async def search(
    db: SessionDep,
    q: str = Query(..., description="Search query (supports quotes, OR, -exclude)"),
    limit: int = Query(20, ge=1, le=100),
) -> list[SearchResult]:
    if not q or not q.strip():
        raise bad_request("EMPTY_QUERY", "Query must not be empty")
    service = SearchService(db)

    client_rows = await service.search_clients(q, limit=limit)
    doc_rows = await service.search_documents_rrf(q, limit=limit)

    results: list[SearchResult] = []

    for row in client_rows:
        results.append(
            ClientResult(
                type="client",
                score=row["score"],
                client=SearchHitClient(
                    id=row["id"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    email=row["email"],
                    description=row["description"],
                    social_links=row["social_links"],
                    created_at=row["created_at"],
                ),
            )
        )

    for row in doc_rows:
        results.append(
            DocumentResult(
                type="document",
                score=row["score"],
                document=SearchHitDocument(
                    id=row["id"],
                    document_id=row["document_id"],
                    client_id=row["client_id"],
                    title=row["title"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                ),
            )
        )

    return results
