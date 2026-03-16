"""
Embedding model factory for the Egyptian Law Assistant.

Responsibilities:
  - Return the correct LlamaIndex BaseEmbedding for the active embedding
    provider (set via EMBEDDING_PROVIDER env var, independent of LLM_PROVIDER).
  - Fail fast with a ConfigurationError for unsupported providers.

Architectural contract:
  This is the ONLY file in the codebase that imports LlamaIndex embedding
  classes. Swapping the embedding backend requires changing only this file.

Provider matrix (embedding_provider → class):
  "cohere"  → CohereEmbedding   — production / cloud (FREE tier, Arabic-native)
  "ollama"  → OllamaEmbedding   — local development only, requires Ollama running
  "claude"  → CohereEmbedding   — generation uses Claude, embeddings use Cohere
  "groq"    → CohereEmbedding   — generation uses Groq,   embeddings use Cohere

Why Cohere embed-multilingual-v3.0?
  - Free tier: 1,000 API calls/month — enough for development and demo traffic.
  - Native Arabic support: trained on 100+ languages including Arabic MSA.
  - 1024-dimension output: same as bge-m3, so no ChromaDB schema change.
  - LlamaIndex integration: first-class, actively maintained.
  - Zero infrastructure: no Ollama server, no GPU, no Docker — pure HTTPS call.

Critical: input_type matters for retrieval quality
  Cohere's Embed v3 is an asymmetric model — the same text embedded with
  different input_type values produces vectors in different subspaces:
    "search_document" → used during ingestion (build_index)
    "search_query"    → used during querying (execute_query)
  Mixing these types causes silent retrieval quality degradation.
  The settings expose EMBEDDING_INPUT_TYPE to let the ingestion script
  and the query pipeline each set the correct value.
"""

from __future__ import annotations

import logging

from llama_index.core.base.embeddings.base import BaseEmbedding

from src.core.config import Settings
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# ── Supported embedding providers ─────────────────────────────────────────────
# Providers that route through Cohere (all cloud/API-based providers)
_COHERE_PROVIDERS = frozenset({"cohere", "groq", "claude"})

# Providers that route through Ollama (local only)
_OLLAMA_PROVIDERS = frozenset({"ollama"})


def get_embedding_model(settings: Settings) -> BaseEmbedding:
    """
    Return a LlamaIndex ``BaseEmbedding`` configured for the active provider.

    The returned object can be passed directly to ``VectorStoreIndex``,
    ``IngestionPipeline``, and ``StorageContext`` without any adapter.

    Provider routing:
      - EMBEDDING_PROVIDER overrides LLM_PROVIDER for embedding selection.
        If EMBEDDING_PROVIDER is not set, it defaults to "cohere" in
        production (groq/claude) and "ollama" in local development.
      - Cohere is used for all cloud providers (groq, claude, cohere).
      - Ollama is used only in local development (llm_provider="ollama"
        AND embedding_provider="ollama").

    Args:
        settings: The active Settings singleton.

    Returns:
        A configured ``BaseEmbedding`` ready for use.

    Raises:
        ConfigurationError: If the provider is unsupported or its required
            API key is absent.
    """
    embed_provider = settings.embedding_provider
    model_name     = settings.embedding_model
    input_type     = settings.embedding_input_type

    logger.info(
        "Embedding provider=%r  model=%r  input_type=%r",
        embed_provider, model_name, input_type,
    )

    # ── Cohere (production — all cloud providers) ──────────────────────────────
    if embed_provider in _COHERE_PROVIDERS:
        return _build_cohere_embedding(settings, model_name, input_type)

    # ── Ollama (local development only) ───────────────────────────────────────
    if embed_provider in _OLLAMA_PROVIDERS:
        return _build_ollama_embedding(settings, model_name)

    raise ConfigurationError(
        setting="embedding_provider",
        reason=(
            f"No embedding implementation for provider {embed_provider!r}. "
            f"Supported: 'cohere' (production), 'ollama' (local dev). "
            f"Set EMBEDDING_PROVIDER in your .env file."
        ),
    )


def _build_cohere_embedding(
    settings: Settings,
    model_name: str,
    input_type: str,
) -> BaseEmbedding:
    """
    Build a CohereEmbedding instance.

    Validates the API key before attempting to construct the client
    so the error message is clear ('missing key') rather than cryptic
    ('connection refused' or '401 Unauthorized').
    """
    from llama_index.embeddings.cohere import CohereEmbedding

    if not settings.cohere_api_key:
        raise ConfigurationError(
            setting="cohere_api_key",
            reason=(
                "COHERE_API_KEY must be set when EMBEDDING_PROVIDER='cohere'. "
                "Get a free key at https://dashboard.cohere.com/api-keys — "
                "no credit card required."
            ),
        )

    api_key = settings.cohere_api_key.get_secret_value()

    logger.info(
        "Initialising CohereEmbedding: model=%r  input_type=%r",
        model_name, input_type,
    )

    return CohereEmbedding(
        cohere_api_key=api_key,
        model_name=model_name,
        # input_type controls which representation subspace is used.
        # MUST be "search_document" during ingestion.
        # MUST be "search_query"    during querying.
        # The scripts/ingest.py overrides this via EMBEDDING_INPUT_TYPE=search_document.
        input_type=input_type,
    )


def _build_ollama_embedding(settings: Settings, model_name: str) -> BaseEmbedding:
    """
    Build an OllamaEmbedding instance for local development.

    Only used when EMBEDDING_PROVIDER=ollama. Not suitable for cloud
    deployment — Render/Vercel free tier has no GPU and cannot run Ollama.
    """
    from llama_index.embeddings.ollama import OllamaEmbedding

    logger.info(
        "Initialising OllamaEmbedding: model=%r  base_url=%r  "
        "(local dev only — not suitable for cloud deployment)",
        model_name, settings.ollama_base_url,
    )

    return OllamaEmbedding(
        model_name=model_name,
        base_url=settings.ollama_base_url,
        request_timeout=120.0,
    )
