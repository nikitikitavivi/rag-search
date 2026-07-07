from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import conflict, not_found
from app.core.db import get_session
from app.schemas.client import ClientCreate, ClientOut, ClientPage
from app.schemas.common import ErrorResponse
from app.services.clients import ClientService, DuplicateEmailError

SessionDep = Annotated[AsyncSession, Depends(get_session)]

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
async def create_client(payload: ClientCreate, db: SessionDep) -> ClientOut:
    svc = ClientService(db)
    try:
        client = await svc.create(payload)
    except DuplicateEmailError as err:
        raise conflict(
            "CLIENT_EMAIL_CONFLICT",
            "A client with this email already exists",
            resource_id=payload.email,
        ) from err
    return ClientOut.model_validate(client)


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
    svc = ClientService(db)
    items, next_cursor, has_more = await svc.list(limit, cursor)
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
) -> ClientOut:
    svc = ClientService(db)
    client = await svc.get_by_email(email)
    if client is None:
        raise not_found("CLIENT_NOT_FOUND", "Client not found", resource_id=email)
    return ClientOut.model_validate(client)


@router.get(
    "/{client_id}",
    response_model=ClientOut,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get a client by id",
)
async def get_client(client_id: UUID, db: SessionDep) -> ClientOut:
    svc = ClientService(db)
    client = await svc.get_by_id(client_id)
    if client is None:
        raise not_found("CLIENT_NOT_FOUND", "Client not found", resource_id=str(client_id))
    return ClientOut.model_validate(client)


@router.get(
    "/{client_id}/count-documents",
    response_model=int,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Count documents for a client (helper)",
    include_in_schema=False,
)
async def count_client_documents(client_id: UUID, db: SessionDep) -> int:
    svc = ClientService(db)
    return await svc.count_documents(client_id)
