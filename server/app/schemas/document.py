from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1, max_length=1_000_000)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    title: str
    content: str
    created_at: datetime


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    client_name: str
    title: str
    content: str
    created_at: datetime


class DocumentPage(BaseModel):
    items: list[DocumentListItem]
    next_cursor: str | None = Field(None, description="Opaque cursor for the next page")
    has_more: bool = Field(False)
    count: int
