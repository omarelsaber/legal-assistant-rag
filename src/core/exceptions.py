"""
Domain exception hierarchy for the Egyptian Law Assistant.

Design principles:
  1. Every exception inherits from EgyptianLawAssistantError so callers can
     catch the entire domain with a single except clause when needed.
  2. Exceptions are plain data classes — zero logic, zero side effects.
  3. LLMProviderError carries a `retryable` flag so the calling layer can
     decide whether to retry or propagate immediately.
  4. The FastAPI exception_handlers.py module maps these types to HTTP status
     codes — the mapping lives there, not here.

Usage:
    from src.core.exceptions import LLMProviderError, EmptyRetrievalError

    raise LLMProviderError(provider="ollama", reason="connection refused", retryable=True)
    raise EmptyRetrievalError(query="ما هو رأس المال؟")
"""


class EgyptianLawAssistantError(Exception):
    """
    Base exception for all domain errors in this application.

    Catching this type will catch every application-specific error
    without catching unrelated Python built-in exceptions.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r})"


# ── LLM Provider Exceptions ───────────────────────────────────────────────────

class LLMProviderError(EgyptianLawAssistantError):
    """
    Raised when an LLM provider call fails.

    The `retryable` flag signals whether the failure is transient
    (e.g., timeout, rate limit) or permanent (e.g., invalid API key,
    unsupported model). Retry logic in the calling layer should inspect
    this flag before deciding to retry.

    Args:
        provider:  Name of the provider that failed ('ollama' or 'claude').
        reason:    Human-readable failure description.
        retryable: True if the operation may succeed on a subsequent attempt.
    """

    def __init__(self, provider: str, reason: str, retryable: bool = False) -> None:
        self.provider = provider
        self.reason = reason
        self.retryable = retryable
        super().__init__(
            f"LLM provider '{provider}' failed (retryable={retryable}): {reason}"
        )

    def __repr__(self) -> str:
        return (
            f"LLMProviderError("
            f"provider={self.provider!r}, "
            f"reason={self.reason!r}, "
            f"retryable={self.retryable})"
        )


# ── Retrieval Exceptions ──────────────────────────────────────────────────────

class RetrievalError(EgyptianLawAssistantError):
    """
    Raised when the vector store retrieval step fails unexpectedly.

    Distinct from EmptyRetrievalError: this indicates a system-level
    failure (e.g., ChromaDB unreachable), not a valid 'no results' state.
    """


class EmptyRetrievalError(RetrievalError):
    """
    Raised when retrieval succeeds but returns zero matching chunks.

    This is a valid application-level outcome (the query has no relevant
    documents in the index), not a system failure. The API layer should
    translate this into a graceful 'no information found' response rather
    than a 500 error.

    Args:
        query: The original query string, for diagnostic logging.
    """

    def __init__(self, query: str) -> None:
        self.query = query
        super().__init__(
            f"No relevant document chunks found for query: {query!r}. "
            "Ensure documents have been ingested and the query language matches the corpus."
        )


# ── Embedding Exceptions ──────────────────────────────────────────────────────

class EmbeddingError(EgyptianLawAssistantError):
    """
    Raised when embedding generation fails.

    Common causes:
      - Embedding model not loaded in Ollama.
      - Dimension mismatch between the embedding model and the ChromaDB collection.
      - Input text is empty or exceeds the model's context window.

    Args:
        model:  Name of the embedding model that failed.
        reason: Description of the failure.
    """

    def __init__(self, model: str, reason: str) -> None:
        self.model = model
        self.reason = reason
        super().__init__(f"Embedding model '{model}' failed: {reason}")


# ── Ingestion Exceptions ──────────────────────────────────────────────────────

class IngestionError(EgyptianLawAssistantError):
    """
    Raised when document ingestion fails for a specific file.

    Designed to be non-fatal at the pipeline level: the ingestion runner
    catches this per-file, records the failure in IngestionResult.failed_files,
    and continues with the remaining batch.

    Args:
        file_path: Path of the document that failed ingestion.
        reason:    Description of the failure.
    """

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Ingestion failed for '{file_path}': {reason}")


# ── Configuration Exceptions ──────────────────────────────────────────────────

class ConfigurationError(EgyptianLawAssistantError):
    """
    Raised when the application is misconfigured at startup.

    This should surface before any request is served — typically triggered
    by the Pydantic Settings model validator (e.g., Claude selected but
    no API key provided) or by a factory function receiving an unknown
    provider name.

    Args:
        setting: Name of the misconfigured setting or component.
        reason:  Description of what is wrong and how to fix it.
    """

    def __init__(self, setting: str, reason: str) -> None:
        self.setting = setting
        self.reason = reason
        super().__init__(f"Configuration error for '{setting}': {reason}")