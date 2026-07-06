from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


DbSession = Depends(get_db)
