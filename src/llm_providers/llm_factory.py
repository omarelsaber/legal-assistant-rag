"""
LLM provider factory for the Egyptian Law Assistant.

All pipeline code calls get_llm(settings) — it never imports provider
classes directly. Swapping providers is a one-line .env change.

IMPORTANT — lazy imports:
  All provider-specific imports (Groq, Ollama, Anthropic) are inside
  their respective if-blocks, NOT at the top of the file. This is
  intentional and critical for Render deployment:

  requirements.txt for Render includes ONLY llama-index-llms-groq.
  If llama-index-llms-ollama and llama-index-llms-anthropic were imported
  at module level, the server would crash at startup with ImportError
  even though those providers are never called.

  Lazy imports mean each package is only imported if that provider is
  actually selected. The server starts cleanly with only groq installed.
"""

from __future__ import annotations

import logging

from llama_index.core.llms import LLM

from src.core.config import Settings
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def get_llm(settings: Settings) -> LLM:
    """
    Return a LlamaIndex LLM for the active provider.

    Imports are lazy — each provider's package is only imported when
    that provider is actually selected, preventing ImportError on
    deployments where optional provider packages are not installed.

    Raises:
        ConfigurationError: If the provider is unknown or its key is missing.
    """
    provider = settings.llm_provider

    # ── Groq (production — import only when selected) ──────────────────────
    if provider == "groq":
        from llama_index.llms.groq import Groq  # lazy — only groq installed on Render

        if not settings.groq_api_key:
            raise ConfigurationError(
                setting="groq_api_key",
                reason=(
                    "GROQ_API_KEY must be set when LLM_PROVIDER='groq'. "
                    "Get a free key at https://console.groq.com/keys"
                ),
            )
        logger.info("Initialising Groq LLM: model=%r", settings.groq_model)
        return Groq(
            model=settings.groq_model,
            api_key=settings.groq_api_key.get_secret_value(),
        )

    # ── Ollama (local dev — import only when selected) ─────────────────────
    if provider == "ollama":
        from llama_index.llms.ollama import Ollama  # lazy — not installed on Render

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

    # ── Claude (premium — import only when selected) ───────────────────────
    if provider == "claude":
        from llama_index.llms.anthropic import Anthropic  # lazy — not installed on Render

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
            f"Unknown provider {provider!r}. "
            f"Supported: 'groq' (production), 'ollama' (local), 'claude' (premium)."
        ),
    )