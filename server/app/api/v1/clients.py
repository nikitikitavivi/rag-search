from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import conflict, not_found
from app.core.cursor import decode_cursor, encode_cursor
from app.core.deps import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientOut, ClientPage
from app.schemas.common import ErrorResponse

SessionDep = Annotated[AsyncSession, Depends(get_db)]

router = APIRouter(prefix="/clients", tags=["clients"])

COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@router.post(
    "",
    response_model=ClientOut,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERRORS,
    summary="Create a client",
)
async def create_client(payload: ClientCreate, db: SessionDep) -> Client:
    client = Client(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        description=payload.description,
        social_links=payload.social_links,
    )
    db.add(client)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise conflict(
            "CLIENT_EMAIL_CONFLICT",
            "A client with this email already exists",
            resource_id=payload.email,
        ) from exc
    await db.refresh(client)
    return client


@router.get(
    "",
    response_model=ClientPage,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List clients (cursor pagination)",
)
async def list_clients(
    db: SessionDep,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Page size"),
    cursor: str | None = Query(None, description="Opaque cursor from the previous page"),
) -> ClientPage:
    stmt = select(Client).order_by(Client.created_at.desc(), Client.id.desc())

    if cursor:
        cursor_ts, cursor_id = decode_cursor(cursor)
        # Keyset: rows strictly before (created_at, id) in DESC order
        stmt = stmt.where(
            (Client.created_at < cursor_ts)
            | ((Client.created_at == cursor_ts) & (Client.id < cursor_id))
        )

    # Fetch limit+1 to determine has_more without a separate count query
    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, str(last.id))

    return ClientPage(
        items=[ClientOut.model_validate(c) for c in items],
        next_cursor=next_cursor,
        has_more=has_more,
        count=len(items),
    )


@router.get(
    "/lookup",
    response_model=ClientOut,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Look up a client by email",
)
async def lookup_client(
    db: SessionDep,
    email: str = Query(..., description="Client email"),
) -> Client:
    result = await db.execute(select(Client).where(Client.email == email))
    client = result.scalar_one_or_none()
    if client is None:
        raise not_found("CLIENT_NOT_FOUND", "Client not found", resource_id=email)
    return client


@router.get(
    "/{client_id}",
    response_model=ClientOut,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get a client by id",
)
async def get_client(client_id: UUID, db: SessionDep) -> Client:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise not_found("CLIENT_NOT_FOUND", "Client not found", resource_id=str(client_id))
    return client


@router.get(
    "/{client_id}/count-documents",
    response_model=int,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Count documents for a client (helper)",
    include_in_schema=False,
)
async def count_client_documents(client_id: UUID, db: SessionDep) -> int:
    from app.models.document import Document

    result = await db.execute(
        select(func.count()).select_from(Document).where(Document.client_id == client_id)
    )
    return int(result.scalar_one())
