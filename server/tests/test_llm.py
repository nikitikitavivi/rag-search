from unittest.mock import MagicMock, patch

import pytest

from app.services.llm import LLMService, get_llm_service, reset_llm_service


class TestLLMService:
    def test_is_available_with_key(self):
        svc = LLMService(api_key="sk-test")
        assert svc.is_available is True

    def test_is_available_without_key(self):
        svc = LLMService(api_key="")
        assert svc.is_available is False

    def test_model_name(self):
        svc = LLMService(model="custom-model")
        assert svc.model_name == "custom-model"

    async def test_summarize_raises_when_not_available(self):
        svc = LLMService(api_key="")
        with pytest.raises(RuntimeError, match="OpenAI API key is not configured"):
            await svc.summarize("some content")

    async def test_document_context_raises_when_not_available(self):
        svc = LLMService(api_key="")
        with pytest.raises(RuntimeError, match="OpenAI API key is not configured"):
            await svc.document_context("title", "content")

    async def test_hypothetical_questions_raises_when_not_available(self):
        svc = LLMService(api_key="")
        with pytest.raises(RuntimeError, match="OpenAI API key is not configured"):
            await svc.hypothetical_questions("chunk text")

    async def test_summarize_calls_api_and_returns_content(self):
        svc = LLMService(api_key="sk-test", model="gpt-4.1-nano")
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "A concise summary."
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.summarize("Document content here.")

        assert result == "A concise summary."
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4.1-nano"
        assert call_kwargs["max_tokens"] == 300
        assert "WealthTech" in call_kwargs["messages"][1]["content"]

    async def test_document_context_calls_api_with_correct_params(self):
        svc = LLMService(api_key="sk-test")
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Context sentence."
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc.document_context("My Title", "Content here.")

        assert result == "Context sentence."
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 150
        assert "Title: My Title" in call_kwargs["messages"][1]["content"]

    async def test_hypothetical_questions_parses_lines(self):
        svc = LLMService(api_key="sk-test")
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Question one\nQuestion two\nQuestion three"
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        with patch.object(svc, "_get_client", return_value=mock_client):
            questions = await svc.hypothetical_questions("Some chunk text.")

        assert questions == ["Question one", "Question two", "Question three"]
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 200

    async def test_hypothetical_questions_strips_bullets_and_dashes(self):
        svc = LLMService(api_key="sk-test")
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "- Question one\n- Question two"
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        with patch.object(svc, "_get_client", return_value=mock_client):
            questions = await svc.hypothetical_questions("Some chunk text.")

        assert questions == ["Question one", "Question two"]

    async def test_hypothetical_questions_skips_empty_lines(self):
        svc = LLMService(api_key="sk-test")
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Question one\n\n\nQuestion two\n"
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        with patch.object(svc, "_get_client", return_value=mock_client):
            questions = await svc.hypothetical_questions("Some chunk text.")

        assert len(questions) == 2

    async def test__call_returns_empty_string_when_content_is_none(self):
        svc = LLMService(api_key="sk-test")
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = await svc._call("system prompt", "user prompt")

        assert result == ""


class TestLLMServiceSingletons:
    def teardown_method(self):
        reset_llm_service()

    def test_get_llm_service_returns_singleton(self):
        reset_llm_service()
        svc1 = get_llm_service()
        svc2 = get_llm_service()
        assert svc1 is svc2

    def test_reset_llm_service_creates_new_instance(self):
        reset_llm_service()
        svc1 = get_llm_service()
        reset_llm_service()
        svc2 = get_llm_service()
        assert svc1 is not svc2
