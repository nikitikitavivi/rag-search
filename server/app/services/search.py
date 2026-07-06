import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embeddings import get_embedding_service

logger = logging.getLogger(__name__)

RRF_K = 60
BM25_WEIGHT = 0.5
MIN_SCORE = 0.1


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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

    async def search_documents_rrf(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = query.strip()
        if not q:
            return []

        emb = get_embedding_service()
        vector_hits: list[tuple[str, float]] = []
        if emb.is_available:
            try:
                q_vec = emb.embed(query)
                vec_str = "[" + ",".join(str(float(v)) for v in q_vec) + "]"
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
                    {"vec": vec_str, "limit": limit * 2},
                )
                for row in vec_result.mappings():
                    vector_hits.append((row["id"], float(row["similarity"])))
            except Exception as exc:
                logger.warning("Vector search failed: %s", exc)

        q_clean = re.sub(r"[@.]", " ", q)
        bm25_hits: list[tuple[str, float]] = []
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
                {"q": q_clean, "limit": limit * 2},
            )
            for row in bm25_result.mappings():
                bm25_hits.append((row["id"], float(row["score"])))
        except Exception as exc:
            logger.warning("BM25 search failed: %s", exc)

        vector_scores: dict[str, float] = {}
        for chunk_id, sim in vector_hits:
            vector_scores[str(chunk_id)] = sim

        bm25_scores: dict[str, float] = {}
        max_bm25 = 0.0
        for chunk_id, score in bm25_hits:
            bm25_scores[str(chunk_id)] = score
            if score > max_bm25:
                max_bm25 = score

        all_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
        use_bm25 = len(bm25_scores) > 0
        use_vec = len(vector_scores) > 0

        if use_bm25 and use_vec:
            w = BM25_WEIGHT
        elif use_bm25:
            w = 1.0
        else:
            w = 0.0

        fused_scores: dict[str, float] = {}
        for chunk_id in all_ids:
            vec = vector_scores.get(chunk_id, 0.0)
            bm = bm25_scores.get(chunk_id, 0.0) / max_bm25 if max_bm25 > 0 else 0.0
            fused_scores[chunk_id] = w * bm + (1 - w) * vec

        sorted_ids = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        if not sorted_ids:
            return []

        rank_map = {chunk_id: i for i, (chunk_id, _) in enumerate(sorted_ids)}

        placeholders = ", ".join(f":id_{i}" for i in range(len(sorted_ids)))
        params: dict[str, Any] = {}
        for i, (chunk_id, _) in enumerate(sorted_ids):
            params[f"id_{i}"] = chunk_id

        docs_result = await self._session.execute(
            text(
                "SELECT dc.id, dc.document_id, dc.content, dc.chunk_index, "
                "d.title, d.client_id "
                "FROM document_chunks dc "
                "JOIN documents d ON d.id = dc.document_id "
                f"WHERE dc.id::text IN ({placeholders})"
            ),
            params,
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
                    "score": fused_scores[chunk_id],
                }
            )
        rows.sort(key=lambda r: rank_map[str(r["id"])])
        rows = [r for r in rows if r["score"] >= MIN_SCORE]
        return rows

