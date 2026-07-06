from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=200)
    last_name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    description: str | None = Field(None, max_length=5000)
    social_links: list[str] | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str
    description: str | None = None
    social_links: list[str] | None = None
    created_at: datetime


class ClientPage(BaseModel):
    """Cursor-paginated response for clients."""
    items: list[ClientOut]
    next_cursor: str | None = Field(
        None, description="Opaque cursor for the next page; null if no more results"
    )
    has_more: bool = Field(False, description="Whether more results exist")
    count: int = Field(..., description="Number of items in this page")
