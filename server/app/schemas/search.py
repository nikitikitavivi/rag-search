from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchHitClient(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str
    description: str | None = None
    social_links: list[str] | None = None
    created_at: datetime


class SearchHitDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    client_id: UUID
    title: str
    chunk_index: int
    content: str


class ClientResult(BaseModel):
    type: Literal["client"] = "client"
    score: float
    client: SearchHitClient


class DocumentResult(BaseModel):
    type: Literal["document"] = "document"
    score: float
    document: SearchHitDocument


SearchResult = ClientResult | DocumentResult
