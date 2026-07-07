import logging
from uuid import UUID

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cursor import decode_cursor, encode_cursor
from app.models.client import Client
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentCreate
from app.services.embeddings import get_embedding_service
from app.services.llm import get_llm_service

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
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, client_id: UUID, payload: DocumentCreate
    ) -> Document:
        client = (
            await self._session.execute(select(Client).where(Client.id == client_id))
        ).scalar_one_or_none()
        if client is None:
            raise ClientNotFoundError(f"Client {client_id} not found")

        document = Document(
            client_id=client_id,
            title=payload.title,
            content=payload.content,
        )
        self._session.add(document)
        await self._session.flush()

        chunks_text = _splitter.split_text(payload.content)
        emb_service = get_embedding_service()
        llm = get_llm_service()

        doc_context = ""
        try:
            doc_context = llm.document_context(payload.title, payload.content)
        except Exception as exc:
            logger.warning("Document context generation failed: %s", exc)

        for i, chunk_text in enumerate(chunks_text):
            questions: list[str] = []
            try:
                questions = llm.hypothetical_questions(chunk_text)
            except Exception as exc:
                logger.warning("Hypothetical questions failed for chunk %d: %s", i, exc)

            enriched = _build_enriched_text(doc_context, questions, chunk_text)

            embedding: list[float] | None = None
            try:
                embedding = emb_service.embed(enriched).tolist()
            except Exception as exc:
                logger.warning("Embedding failed for chunk %d: %s", i, exc)

            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=i,
                content=chunk_text,
                enriched_content=enriched,
                search_text=f"{payload.title}\n{chunk_text}",
                embedding=embedding,
                chunk_metadata={
                    "document_title": payload.title,
                    "client_id": str(client_id),
                },
            )
            self._session.add(chunk)

        await self._session.commit()
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
        rows = list(result.all())

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
