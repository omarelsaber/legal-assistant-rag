"""
Embedding model factory for the Egyptian Law Assistant.

IMPORTANT — lazy imports (same rationale as llm_factory.py):
  OllamaEmbedding and CohereEmbedding are imported inside their
  builder functions, not at module level. On Render, only
  llama-index-embeddings-cohere is installed. If llama-index-embeddings-ollama
  were imported at the top of this file, the server would crash at
  startup even though Ollama is never used in production.
"""

from __future__ import annotations

import logging

from llama_index.core.base.embeddings.base import BaseEmbedding

from src.core.config import Settings
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_COHERE_PROVIDERS = frozenset({"cohere", "groq", "claude"})
_OLLAMA_PROVIDERS = frozenset({"ollama"})


def get_embedding_model(settings: Settings) -> BaseEmbedding:
    """
    Return a LlamaIndex BaseEmbedding for the active embedding provider.

    Provider routing:
      cohere / groq / claude → CohereEmbedding (cloud, free tier, Arabic-native)
      ollama                 → OllamaEmbedding (local dev only, not on Render)

    Raises:
        ConfigurationError: If provider is unknown or required key is missing.
    """
    embed_provider = settings.embedding_provider
    model_name     = settings.embedding_model
    input_type     = settings.embedding_input_type

    logger.info(
        "Embedding provider=%r  model=%r  input_type=%r",
        embed_provider, model_name, input_type,
    )

    if embed_provider in _COHERE_PROVIDERS:
        return _build_cohere_embedding(settings, model_name, input_type)

    if embed_provider in _OLLAMA_PROVIDERS:
        return _build_ollama_embedding(settings, model_name)

    raise ConfigurationError(
        setting="embedding_provider",
        reason=(
            f"Unknown embedding provider {embed_provider!r}. "
            f"Supported: 'cohere' (production), 'ollama' (local dev)."
        ),
    )


def _build_cohere_embedding(
    settings: Settings,
    model_name: str,
    input_type: str,
) -> BaseEmbedding:
    from llama_index.embeddings.cohere import CohereEmbedding  # lazy import

    if not settings.cohere_api_key:
        raise ConfigurationError(
            setting="cohere_api_key",
            reason=(
                "COHERE_API_KEY must be set when EMBEDDING_PROVIDER='cohere'. "
                "Free at https://dashboard.cohere.com/api-keys"
            ),
        )

    logger.info(
        "Initialising CohereEmbedding: model=%r  input_type=%r",
        model_name, input_type,
    )
    return CohereEmbedding(
        cohere_api_key=settings.cohere_api_key.get_secret_value(),
        model_name=model_name,
        input_type=input_type,
    )


def _build_ollama_embedding(settings: Settings, model_name: str) -> BaseEmbedding:
    from llama_index.embeddings.ollama import OllamaEmbedding  # lazy import

    logger.info(
        "Initialising OllamaEmbedding: model=%r  (local dev only)",
        model_name,
    )
    return OllamaEmbedding(
        model_name=model_name,
        base_url=settings.ollama_base_url,
        request_timeout=120.0,
    )
