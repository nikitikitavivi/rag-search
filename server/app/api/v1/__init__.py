from fastapi import APIRouter

from app.api.v1 import clients, documents, search

api_router = APIRouter(prefix="/v1")
api_router.include_router(clients.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
