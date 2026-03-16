"""
LLM provider factory for the Egyptian Law Assistant.

All pipeline code calls get_llm(settings) — it never imports provider
classes directly. Swapping providers is a one-line .env change.

Provider mapping:
  "ollama" → Ollama (local)     — development
  "claude" → Anthropic Claude   — premium
  "groq"   → Groq Cloud API     — production free tier (recommended)

Arabic compatibility note:
  All three providers are fully compatible with the strict Arabic QA prompt
  and response_mode="simple_summarize" in query_pipeline.py.
  Groq's llama3-70b-8192 provides significantly better Arabic instruction-
  following than the 8B variant — always prefer 70b for Arabic legal text.
"""

from __future__ import annotations

import logging

from llama_index.core.llms import LLM
from llama_index.llms.anthropic import Anthropic
from llama_index.llms.groq import Groq
from llama_index.llms.ollama import Ollama

from src.core.config import Settings
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def get_llm(settings: Settings) -> LLM:
    """
    Return a LlamaIndex ``LLM`` instance for the active provider.

    The returned object is typed as ``LLM`` (LlamaIndex base class) so
    query_pipeline.py is decoupled from any concrete provider type.

    Args:
        settings: Active Settings singleton.

    Returns:
        A configured LlamaIndex ``LLM`` ready for use in a query engine.

    Raises:
        ConfigurationError: If the provider is unrecognised or its required
            API key is missing.
    """
    provider = settings.llm_provider

    # ── Groq (production free tier) ───────────────────────────────────────────
    if provider == "groq":
        if not settings.groq_api_key:
            raise ConfigurationError(
                setting="groq_api_key",
                reason=(
                    "GROQ_API_KEY must be set when LLM_PROVIDER='groq'. "
                    "Get a free key at https://console.groq.com/keys"
                ),
            )
        logger.info(
            "Initialising Groq LLM: model=%r",
            settings.groq_model,
        )
        return Groq(
            model=settings.groq_model,
            api_key=settings.groq_api_key.get_secret_value(),
        )

    # ── Ollama (local development) ────────────────────────────────────────────
    if provider == "ollama":
        logger.info(
            "Initialising Ollama LLM: model=%r  base_url=%r",
            settings.ollama_model,
            settings.ollama_base_url,
        )
        return Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            request_timeout=120.0,
        )

    # ── Claude (Anthropic API) ────────────────────────────────────────────────
    if provider == "claude":
        if not settings.claude_api_key:
            raise ConfigurationError(
                setting="claude_api_key",
                reason="CLAUDE_API_KEY must be set when LLM_PROVIDER='claude'.",
            )
        logger.info("Initialising Claude LLM: model=%r", settings.claude_model)
        return Anthropic(
            model=settings.claude_model,
            api_key=settings.claude_api_key.get_secret_value(),
            max_tokens=2048,
        )

    # ── Unknown provider ──────────────────────────────────────────────────────
    raise ConfigurationError(
        setting="llm_provider",
        reason=(
            f"No LLM implementation registered for provider {provider!r}. "
            f"Supported: 'groq', 'ollama', 'claude'. "
            f"Update LLM_PROVIDER in your .env file."
        ),
    )