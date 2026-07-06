from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., examples=["CLIENT_NOT_FOUND"])
    message: str = Field(..., examples=["Client not found"])
    resource_id: str | None = Field(None, examples=["uuid-or-null"])


class ErrorResponse(BaseModel):
    detail: ErrorDetail
