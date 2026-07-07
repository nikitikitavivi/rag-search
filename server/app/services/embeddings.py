import asyncio
import logging
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.openai_embeddings_api_key
        self._model_name = model or settings.openai_embeddings_model
        self._client: Any | None = None

    @property
    def dim(self) -> int:
        return 1536

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import OpenAI

        self._client = OpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, text: str) -> np.ndarray:
        if not self.is_available:
            raise RuntimeError("OpenAI embeddings API key is not configured")
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        def _run() -> np.ndarray:
            client = self._get_client()
            resp = client.embeddings.create(
                model=self._model_name,
                input=text,
            )
            vec = resp.data[0].embedding
            return np.asarray(vec, dtype=np.float32)

        return await asyncio.to_thread(_run)

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        if not self.is_available:
            raise RuntimeError("OpenAI embeddings API key is not configured")

        def _run() -> list[np.ndarray]:
            client = self._get_client()
            resp = client.embeddings.create(
                model=self._model_name,
                input=texts,
            )
            return [np.asarray(d.embedding, dtype=np.float32) for d in resp.data]

        return await asyncio.to_thread(_run)


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def reset_embedding_service() -> None:
    global _embedding_service
    _embedding_service = None
