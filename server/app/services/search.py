import asyncio
import logging
import re
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

RRF_K = 60
VECTOR_SIMILARITY_THRESHOLD = 0.35


class SearchService:
    def __init__(self, session: AsyncSession, emb_service: EmbeddingService) -> None:
        self._session = session
        self._emb = emb_service

    async def search_clients(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = query.strip()
        if not q:
            return []
        q = re.sub(r"[@.]", " ", q)
        stmt = text(
            """
            SELECT
                c.id, c.first_name, c.last_name, c.email,
                c.description, c.social_links,
                c.created_at,
                ts_rank(c.search_doc, websearch_to_tsquery('simple', :q)) AS score
            FROM clients c
            WHERE c.search_doc @@ websearch_to_tsquery('simple', :q)
            ORDER BY score DESC
            LIMIT :limit
            """
        )
        result = await self._session.execute(stmt, {"q": q, "limit": limit})
        rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def _vector_search(self, q: str, limit: int) -> list[tuple[str, float]]:
        if not self._emb.is_available:
            return []
        try:
            q_vec = await self._emb.embed(q)
            stmt = text(
                "SELECT dc.id, "
                "1 - (dc.embedding <=> cast(:vec as vector)) AS similarity "
                "FROM document_chunks dc "
                "WHERE dc.embedding IS NOT NULL "
                "ORDER BY dc.embedding <=> cast(:vec as vector) "
                "LIMIT :limit"
            )
            vec_result = await self._session.execute(
                stmt,
                {"vec": q_vec.tolist() if hasattr(q_vec, "tolist") else q_vec, "limit": limit},
            )
            hits: list[tuple[str, float]] = []
            for row in vec_result.mappings():
                sim = float(row["similarity"])
                if sim >= VECTOR_SIMILARITY_THRESHOLD:
                    hits.append((row["id"], sim))
            return hits
        except Exception:
            logger.warning("Vector search failed", exc_info=True)
            return []

    async def _bm25_search(self, q: str, limit: int) -> list[tuple[str, float]]:
        q_clean = re.sub(r"[@.]", " ", q)
        try:
            bm25_result = await self._session.execute(
                text(
                    "SELECT dc.id, "
                    "ts_rank(dc.search_doc, websearch_to_tsquery('simple', :q)) AS score "
                    "FROM document_chunks dc "
                    "WHERE dc.search_doc @@ websearch_to_tsquery('simple', :q) "
                    "ORDER BY score DESC "
                    "LIMIT :limit"
                ),
                {"q": q_clean, "limit": limit},
            )
            return [(row["id"], float(row["score"])) for row in bm25_result.mappings()]
        except Exception:
            logger.warning("BM25 search failed", exc_info=True)
            return []

    @staticmethod
    def _rrf_merge(
        vector_hits: list[tuple[str, float]],
        bm25_hits: list[tuple[str, float]],
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        for rank, (chunk_id, _) in enumerate(vector_hits, start=1):
            cid = str(chunk_id)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        for rank, (chunk_id, _) in enumerate(bm25_hits, start=1):
            cid = str(chunk_id)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        return scores

    async def search_documents_rrf(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = query.strip()
        if not q:
            return []

        results = await asyncio.gather(
            self._vector_search(q, limit * 2),
            self._bm25_search(q, limit * 2),
            return_exceptions=True,
        )

        vector_hits: list[tuple[str, float]] = results[0] if isinstance(results[0], list) else []
        bm25_hits: list[tuple[str, float]] = results[1] if isinstance(results[1], list) else []

        if not vector_hits and not bm25_hits:
            return []

        rrf_scores = self._rrf_merge(vector_hits, bm25_hits)

        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        id_list = [uuid.UUID(chunk_id) for chunk_id, _ in sorted_ids]

        return await self._fetch_document_chunks(id_list, rrf_scores)

    async def _fetch_document_chunks(
        self,
        ids: list[uuid.UUID],
        scores: dict[str, float],
    ) -> list[dict[str, Any]]:
        docs_result = await self._session.execute(
            text(
                "SELECT dc.id, dc.document_id, dc.content, dc.chunk_index, "
                "d.title, d.client_id "
                "FROM document_chunks dc "
                "JOIN documents d ON d.id = dc.document_id "
                "WHERE dc.id = ANY(:ids)"
            ),
            {"ids": ids},
        )
        rows = []
        for row in docs_result.mappings():
            chunk_id = str(row["id"])
            rows.append(
                {
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "client_id": row["client_id"],
                    "title": row["title"],
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                    "score": scores[chunk_id],
                }
            )
        rows.sort(key=lambda r: scores.get(str(r["id"]), 0), reverse=True)
        return rows
