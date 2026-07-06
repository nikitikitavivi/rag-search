import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model = model or settings.openai_model
        self._client: Any | None = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import OpenAI

        self._client = OpenAI(api_key=self._api_key)
        return self._client

    def _call(self, system: str, user: str, max_tokens: int = 300) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

    def summarize(self, content: str) -> str:
        if not self.is_available:
            raise RuntimeError("OpenAI API key is not configured")
        prompt = (
            "You are a concise summarizer for a WealthTech document archive. "
            "Summarize the document below in 2-4 sentences. "
            "Answer only from the document content. "
            "If the content is empty or meaningless, say: 'No content to summarize.'\n\n"
            f"Document content:\n{content[:8000]}"
        )
        return self._call("You are a helpful assistant.", prompt, max_tokens=300)

    def document_context(self, title: str, content: str) -> str:
        if not self.is_available:
            raise RuntimeError("OpenAI API key is not configured")
        prompt = (
            "You are a document indexing assistant for a WealthTech platform. "
            "Write a single sentence that captures what this document is about — "
            "the type of document, the parties involved, and the key subject. "
            "This sentence will be prepended to search-indexed chunks to improve retrieval.\n\n"
            f"Title: {title}\n\nContent:\n{content[:4000]}"
        )
        return self._call("You are a helpful assistant.", prompt, max_tokens=150)

    def hypothetical_questions(self, chunk_text: str) -> list[str]:
        if not self.is_available:
            raise RuntimeError("OpenAI API key is not configured")
        prompt = (
            "You are a search-quality assistant. Given the text chunk below, "
            "generate 2-3 questions that a financial advisor might ask which "
            "this chunk would answer. Return each question on a new line. "
            "No numbering, no extra text.\n\n"
            f"Chunk:\n{chunk_text[:3000]}"
        )
        raw = self._call("You are a helpful assistant.", prompt, max_tokens=200)
        return [line.strip("- ").strip() for line in raw.split("\n") if line.strip()]


_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _service
    if _service is None:
        _service = LLMService()
    return _service


def reset_llm_service() -> None:
    global _service
    _service = None
