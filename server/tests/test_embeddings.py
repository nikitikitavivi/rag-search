from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.embeddings import (
    EmbeddingService,
    get_embedding_service,
    reset_embedding_service,
)


class TestEmbeddingService:
    def test_dim_property(self):
        svc = EmbeddingService()
        assert svc.dim == 1536

    def test_is_available_with_key(self):
        svc = EmbeddingService(api_key="sk-test")
        assert svc.is_available is True

    def test_is_available_without_key(self):
        svc = EmbeddingService(api_key="")
        assert svc.is_available is False

    def test_embed_raises_when_not_available(self):
        svc = EmbeddingService(api_key="")
        with pytest.raises(RuntimeError, match="OpenAI embeddings API key is not configured"):
            svc.embed("some text")

    def test_embed_raises_on_empty_text(self):
        svc = EmbeddingService(api_key="sk-test")
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            svc.embed("")

    def test_embed_raises_on_whitespace_text(self):
        svc = EmbeddingService(api_key="sk-test")
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            svc.embed("   ")

    def test_embed_returns_correct_dimensions(self):
        svc = EmbeddingService(api_key="sk-test", model="text-embedding-3-small")
        fake_vec = [0.1] * 1536

        mock_client = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = fake_vec
        mock_client.embeddings.create.return_value.data = [mock_data]

        with patch.object(svc, "_get_client", return_value=mock_client):
            result = svc.embed("test text")

        assert isinstance(result, np.ndarray)
        assert result.shape == (1536,)
        assert result.dtype == np.float32

        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="test text",
        )

    def test_embed_calls_api_with_correct_model(self):
        svc = EmbeddingService(api_key="sk-test", model="custom-model")
        fake_vec = [0.5] * 1536

        mock_client = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = fake_vec
        mock_client.embeddings.create.return_value.data = [mock_data]

        with patch.object(svc, "_get_client", return_value=mock_client):
            svc.embed("hello world")

        mock_client.embeddings.create.assert_called_once_with(
            model="custom-model",
            input="hello world",
        )

    def test__get_client_reuses_instance(self):
        svc = EmbeddingService(api_key="sk-test")
        with patch("openai.OpenAI") as mock_openai:
            client1 = svc._get_client()
            client2 = svc._get_client()
            assert client1 is client2
            mock_openai.assert_called_once()


class TestEmbeddingServiceSingletons:
    def teardown_method(self):
        reset_embedding_service()

    def test_get_embedding_service_returns_singleton(self):
        reset_embedding_service()
        svc1 = get_embedding_service()
        svc2 = get_embedding_service()
        assert svc1 is svc2

    def test_reset_embedding_service_creates_new_instance(self):
        reset_embedding_service()
        svc1 = get_embedding_service()
        reset_embedding_service()
        svc2 = get_embedding_service()
        assert svc1 is not svc2
