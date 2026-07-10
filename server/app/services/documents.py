import asyncio
import logging
from typing import cast
from uuid import UUID

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursor import decode_cursor, encode_cursor
from app.models.client import Client
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentCreate
from app.services.embeddings import EmbeddingService
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


class ClientNotFoundError(Exception):
    pass


def _build_enriched_text(doc_context: str, questions: list[str], chunk_content: str) -> str:
    parts: list[str] = []
    if doc_context.strip():
        parts.append(doc_context.strip())
    for q in questions:
        q = q.strip()
        if q:
            parts.append(q)
    parts.append(chunk_content)
    return "\n".join(parts)


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        emb_service: EmbeddingService,
        llm_service: LLMService,
    ) -> None:
        self._session = session
        self._emb_service = emb_service
        self._llm_service = llm_service

    async def create(
        self, client_id: UUID, payload: DocumentCreate
    ) -> Document:
        result = await self._session.execute(select(Client).where(Client.id == client_id))
        client = result.scalar_one_or_none()
        if client is None:
            raise ClientNotFoundError(f"Client {client_id} not found")

        try:
            chunks_text = _splitter.split_text(payload.content)

            doc_context = ""
            per_chunk_enrichments: list[str] = []

            if self._llm_service.is_available:
                tasks = [
                    self._llm_service.document_context(payload.title, payload.content),
                ] + [
                    self._llm_service.hypothetical_questions(chunk)
                    for chunk in chunks_text
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                doc_context_raw = results[0]
                if isinstance(doc_context_raw, BaseException):
                    logger.warning("Document context generation failed", exc_info=doc_context_raw)
                else:
                    doc_context = cast(str, doc_context_raw)

                for i, chunk_text in enumerate(chunks_text):
                    qs_raw = results[i + 1]
                    questions: list[str] = []
                    if isinstance(qs_raw, BaseException):
                        logger.warning(
                            "Hypothetical questions failed for chunk %d", i, exc_info=qs_raw
                        )
                    else:
                        questions = cast(list[str], qs_raw)
                    per_chunk_enrichments.append(
                        _build_enriched_text(doc_context, questions, chunk_text)
                    )
            else:
                per_chunk_enrichments = [
                    _build_enriched_text("", [], chunk) for chunk in chunks_text
                ]

            embeddings: list[list[float] | None] = [None] * len(chunks_text)
            if self._emb_service.is_available and per_chunk_enrichments:
                vectors = await self._emb_service.embed_batch(per_chunk_enrichments)
                embeddings = [v.tolist() for v in vectors]

            document = Document(
                client_id=client_id,
                title=payload.title,
                content=payload.content,
            )
            self._session.add(document)
            await self._session.flush()

            for i, chunk_text in enumerate(chunks_text):
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    content=chunk_text,
                    enriched_content=per_chunk_enrichments[i],
                    search_text=f"{payload.title}\n{chunk_text}",
                    embedding=embeddings[i],
                    chunk_metadata={
                        "document_title": payload.title,
                        "client_id": str(client_id),
                    },
                )
                self._session.add(chunk)

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        await self._session.refresh(document)
        return document

    async def list(
        self, limit: int, cursor: str | None
    ) -> tuple[list[tuple[Document, Client]], str | None, bool]:
        stmt = (
            select(Document, Client)
            .join(Client, Client.id == Document.client_id)
            .order_by(Document.created_at.desc(), Document.id.desc())
        )

        if cursor:
            cursor_ts, cursor_id = decode_cursor(cursor)
            stmt = stmt.where(
                (Document.created_at < cursor_ts)
                | ((Document.created_at == cursor_ts) & (Document.id < cursor_id))
            )

        stmt = stmt.limit(limit + 1)
        result = await self._session.execute(stmt)
        rows = [tuple(r) for r in result.all()]

        has_more = len(rows) > limit
        rows = rows[:limit]

        next_cursor = None
        if has_more and rows:
            last_doc, _ = rows[-1]
            next_cursor = encode_cursor(last_doc.created_at, str(last_doc.id))

        return rows, next_cursor, has_more

    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()
