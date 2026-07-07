from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursor import decode_cursor, encode_cursor
from app.models.client import Client
from app.models.document import Document
from app.schemas.client import ClientCreate


class DuplicateEmailError(Exception):
    pass


class ClientService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, payload: ClientCreate) -> Client:
        client = Client(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            description=payload.description,
            social_links=payload.social_links,
        )
        self._session.add(client)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if (
                exc.orig
                and hasattr(exc.orig, "diag")
                and exc.orig.diag.constraint_name == "clients_email_key"
            ):
                raise DuplicateEmailError(
                    f"Client with email {payload.email} already exists"
                ) from exc
            raise
        await self._session.refresh(client)
        return client

    async def list(
        self, limit: int, cursor: str | None
    ) -> tuple[list[Client], str | None, bool]:
        stmt = select(Client).order_by(Client.created_at.desc(), Client.id.desc())

        if cursor:
            cursor_ts, cursor_id = decode_cursor(cursor)
            stmt = stmt.where(
                (Client.created_at < cursor_ts)
                | ((Client.created_at == cursor_ts) & (Client.id < cursor_id))
            )

        stmt = stmt.limit(limit + 1)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(last.created_at, str(last.id))

        return items, next_cursor, has_more

    async def get_by_email(self, email: str) -> Client | None:
        result = await self._session.execute(
            select(Client).where(Client.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, client_id: UUID) -> Client | None:
        result = await self._session.execute(
            select(Client).where(Client.id == client_id)
        )
        return result.scalar_one_or_none()

    async def count_documents(self, client_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Document).where(Document.client_id == client_id)
        )
        return int(result.scalar_one())
