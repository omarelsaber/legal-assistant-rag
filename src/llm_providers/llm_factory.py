"""
LLM provider factory for the Egyptian Law Assistant.

Returns a LlamaIndex-compatible LLM object for the active provider.
All pipeline code calls get_llm(settings) — it never imports Ollama or
Anthropic classes directly. Swapping providers is a one-line .env change.

Sprint note:
  This is the minimal factory needed for Sprint 4 (query pipeline).
  Full provider implementations with retry logic, streaming support, and
  contract tests live in Sprint 5 (llm_providers context).
"""

from __future__ import annotations

import logging

from llama_index.core.llms import LLM
from llama_index.llms.anthropic import Anthropic
from llama_index.llms.ollama import Ollama

from src.core.config import Settings
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def get_llm(settings: Settings) -> LLM:
    """
    Return a LlamaIndex ``LLM`` instance for the active provider.

    Provider mapping:
      - ``"ollama"``  → ``llama_index.llms.ollama.Ollama``
      - ``"claude"``  → ``llama_index.llms.anthropic.Anthropic``
      - anything else → raises ``ConfigurationError`` at call time

    The returned object is typed as ``LLM`` (LlamaIndex base class) so
    query_pipeline.py is decoupled from any concrete provider type.

    Args:
        settings: Active Settings singleton.

    Returns:
        A configured LlamaIndex ``LLM`` ready for use in a query engine.

    Raises:
        ConfigurationError: If the provider is unrecognised, or if
            ``CLAUDE_API_KEY`` is absent when provider is ``"claude"``.
            (The latter is also caught by the Pydantic model validator in
            Settings, so this is a belt-and-suspenders guard.)
    """
    provider = settings.llm_provider

    if provider == "ollama":
        logger.info(
            "Initialising Ollama LLM: model=%r  base_url=%r",
            settings.ollama_model,
            settings.ollama_base_url,
        )
        return Ollama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            request_timeout=120.0,   # generous timeout for first-token on cold models
        )

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

    raise ConfigurationError(
        setting="llm_provider",
        reason=(
            f"No LLM implementation registered for provider {provider!r}. "
            f"Supported: 'ollama', 'claude'. "
            f"To add a provider, extend get_llm() in src/llm_providers/llm_factory.py."
        ),
    )