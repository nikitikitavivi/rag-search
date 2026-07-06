from fastapi import HTTPException

from app.schemas.common import ErrorDetail


def not_found(code: str, message: str, resource_id: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=ErrorDetail(code=code, message=message, resource_id=resource_id).model_dump(),
    )


def conflict(code: str, message: str, resource_id: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=ErrorDetail(code=code, message=message, resource_id=resource_id).model_dump(),
    )


def bad_request(code: str, message: str, resource_id: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=ErrorDetail(code=code, message=message, resource_id=resource_id).model_dump(),
    )


def unavailable(code: str, message: str, resource_id: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=ErrorDetail(code=code, message=message, resource_id=resource_id).model_dump(),
    )
