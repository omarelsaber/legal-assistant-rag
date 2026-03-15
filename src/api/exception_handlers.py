"""
FastAPI exception handlers for the Egyptian Law Assistant API.

These handlers translate domain exceptions into structured HTTP responses
with consistent JSON error envelopes. They are the single mapping layer
between the exception hierarchy (``src/core/exceptions.py``) and HTTP
status codes — that mapping lives here and nowhere else.

Error envelope format (all responses):
    {
        "error": {
            "type":      "EmptyRetrievalError",
            "message":   "No relevant articles found for query: '...'",
            "detail":    { ... exception-specific fields ... },
            "retryable": false
        }
    }

A consistent envelope means the React frontend needs one error-handling
code path, not one per status code. The ``retryable`` flag lets the client
decide whether to show "Try again" or "Contact support".

Registration:
    These are plain functions, not decorators. They are registered in
    ``main.py`` via ``app.add_exception_handler()`` — keeping this module
    free of any FastAPI ``app`` import, which would create a circular
    dependency.

Handler registration order in main.py (most specific first):
    EmptyRetrievalError  → 404
    LLMProviderError     → 503 (+ Retry-After header when retryable)
    EmbeddingError       → 503
    ConfigurationError   → 500
    IngestionError       → 500
    RetrievalError       → 500   (base; catches non-Empty retrieval failures)
    EgyptianLawAssistantError → 500  (catch-all for any unclassified domain error)

    FastAPI matches the most-derived type first when multiple handlers are
    registered, so the order of add_exception_handler() calls matters for
    types in the same inheritance chain.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from src.core.exceptions import (
    ConfigurationError,
    EgyptianLawAssistantError,
    EmbeddingError,
    EmptyRetrievalError,
    IngestionError,
    LLMProviderError,
    RetrievalError,
)

logger = logging.getLogger(__name__)

# ── Error envelope builder ─────────────────────────────────────────────────────

def _error_response(
    status_code: int,
    error_type: str,
    message: str,
    detail: dict | None = None,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """
    Build a structured ``JSONResponse`` with the standard error envelope.

    Args:
        status_code: HTTP status code (404, 500, 503, etc.).
        error_type:  Exception class name — used by clients to branch on
                     error type without parsing the message string.
        message:     Human-readable error description.
        detail:      Optional dict of exception-specific fields (e.g.,
                     ``{"provider": "ollama", "reason": "connection refused"}``).
        retryable:   Whether the client should retry the request.
        headers:     Optional extra HTTP response headers (e.g., Retry-After).

    Returns:
        A ``JSONResponse`` with the standard envelope and given status code.
    """
    body = {
        "error": {
            "type":      error_type,
            "message":   message,
            "detail":    detail or {},
            "retryable": retryable,
        }
    }
    return JSONResponse(status_code=status_code, content=body, headers=headers)

# ── Domain exception handlers ──────────────────────────────────────────────────

async def handle_empty_retrieval_error(
    request: Request,
    exc: EmptyRetrievalError,
) -> JSONResponse:
    """
    Handle ``EmptyRetrievalError`` → HTTP 404.

    404 is semantically correct here: the client asked for information
    about a topic that has no relevant articles in the index. It is not
    a server error — the server worked correctly and found nothing.

    The response body includes the original query so the client can display
    a helpful "no results for: '...'" message without re-parsing the URL.
    """
    logger.info(
        "EmptyRetrievalError for query %r — returning 404",
        getattr(exc, "query", "")[:80],
    )

    return _error_response(
        status_code=404,
        error_type="EmptyRetrievalError",
        message="No relevant legal articles were found for your query.",
        detail={"query": getattr(exc, "query", "")},
        retryable=False,
    )

async def handle_llm_provider_error(
    request: Request,
    exc: LLMProviderError,
) -> JSONResponse:
    """
    Handle ``LLMProviderError`` → HTTP 503 Service Unavailable.

    503 signals that the server is temporarily unable to handle the request
    (Ollama is down, Claude API is rate-limiting, etc.) and the client
    should try again later.

    When ``exc.retryable`` is True, a ``Retry-After: 60`` header is added.
    This is a hint to API gateways and well-behaved clients — the value of
    60 seconds is conservative but safe for both Ollama cold-starts and
    Claude rate-limit windows.
    """
    logger.warning(
        "LLMProviderError: provider=%r  retryable=%r  reason=%r",
        exc.provider,
        exc.retryable,
        exc.reason,
    )

    headers = {"Retry-After": "60"} if exc.retryable else None

    return _error_response(
        status_code=503,
        error_type="LLMProviderError",
        message=f"The language model service is currently unavailable: {exc.reason}",
        detail={"provider": exc.provider, "reason": exc.reason},
        retryable=exc.retryable,
        headers=headers,
    )

async def handle_embedding_error(
    request: Request,
    exc: EmbeddingError,
) -> JSONResponse:
    """
    Handle ``EmbeddingError`` → HTTP 503 Service Unavailable.

    Embedding failures are typically caused by Ollama being unreachable
    or the embedding model not being loaded — transient infrastructure
    issues, not client errors.
    """
    logger.error(
        "EmbeddingError: model=%r  reason=%r",
        exc.model,
        exc.reason,
    )

    return _error_response(
        status_code=503,
        error_type="EmbeddingError",
        message=f"The embedding service failed: {exc.reason}",
        detail={"model": exc.model, "reason": exc.reason},
        retryable=True,
        headers={"Retry-After": "30"},
    )

async def handle_configuration_error(
    request: Request,
    exc: ConfigurationError,
) -> JSONResponse:
    """
    Handle ``ConfigurationError`` → HTTP 500 Internal Server Error.

    A ``ConfigurationError`` means the server is misconfigured (e.g.,
    LLM_PROVIDER=claude but no CLAUDE_API_KEY set). This is never the
    client's fault. The response deliberately omits the raw setting value
    to avoid leaking secrets in error messages.
    """
    logger.critical(
        "ConfigurationError: setting=%r  reason=%r — server is misconfigured",
        exc.setting,
        exc.reason,
    )

    return _error_response(
        status_code=500,
        error_type="ConfigurationError",
        message="The server is misconfigured. Please contact the administrator.",
        detail={"setting": exc.setting},
        retryable=False,
    )

async def handle_ingestion_error(
    request: Request,
    exc: IngestionError,
) -> JSONResponse:
    """
    Handle ``IngestionError`` → HTTP 500 Internal Server Error.

    If an ingestion error reaches the API layer it means the query service
    tried to load an index that failed (e.g., no documents were ingested).
    This is a server-side data issue, not a client error.
    """
    logger.error(
        "IngestionError via API: file_path=%r  reason=%r",
        exc.file_path,
        exc.reason,
    )

    return _error_response(
        status_code=500,
        error_type="IngestionError",
        message=(
            "The document index is not ready. "
            "Ensure the ingestion pipeline has been run successfully."
        ),
        detail={"reason": exc.reason},
        retryable=False,
    )

async def handle_retrieval_error(
    request: Request,
    exc: RetrievalError,
) -> JSONResponse:
    """
    Handle ``RetrievalError`` (base, non-empty) → HTTP 500.

    This catches retrieval failures that are NOT EmptyRetrievalError
    (which has its own 404 handler). A base ``RetrievalError`` indicates
    a system failure in the vector store layer — ChromaDB unreachable,
    index corrupted, etc.
    """
    logger.error("RetrievalError: %s", exc.message)

    return _error_response(
        status_code=500,
        error_type="RetrievalError",
        message="An error occurred while searching the document index.",
        detail={"reason": exc.message},
        retryable=False,
    )

async def handle_domain_error(
    request: Request,
    exc: EgyptianLawAssistantError,
) -> JSONResponse:
    """
    Catch-all handler for any ``EgyptianLawAssistantError`` subclass that
    does not have a more specific handler registered.

    This is the safety net. If a new exception subclass is added to
    ``exceptions.py`` without a corresponding handler here, it will be
    caught by this handler and returned as a 500 rather than leaking a raw
    Python traceback to the client.

    The presence of an unclassified domain error in production logs is a
    signal to add a specific handler for it.
    """
    logger.error(
        "Unhandled domain error (%s): %s",
        type(exc).__name__,
        exc.message,
    )

    return _error_response(
        status_code=500,
        error_type=type(exc).__name__,
        message="An unexpected error occurred. Please try again later.",
        detail={"reason": exc.message},
        retryable=False,
    )

# ── Registration helper ────────────────────────────────────────────────────────

def register_exception_handlers(app: object) -> None:
    """
    Register all domain exception handlers on the FastAPI ``app`` instance.

    Called once in ``main.py`` during app construction. Centralising
    registration here (rather than using ``@app.exception_handler`` decorators)
    keeps this module free of any ``app`` import and makes the registration
    order explicit and reviewable in one place.

    Registration order: most-specific subclass before base class.
    FastAPI matches the first registered handler whose type is an exact
    match or base class of the raised exception. Registering the base class
    first would swallow all subclasses into the catch-all handler.

    Args:
        app: The FastAPI application instance. Typed as ``object`` to avoid
             importing FastAPI here (which would create an unnecessary
             coupling — this module only needs ``add_exception_handler``).
    """
    # Most-specific first within each inheritance chain
    app.add_exception_handler(EmptyRetrievalError,       handle_empty_retrieval_error)   # noqa
    app.add_exception_handler(LLMProviderError,          handle_llm_provider_error)      # noqa
    app.add_exception_handler(EmbeddingError,            handle_embedding_error)        # noqa
    app.add_exception_handler(ConfigurationError,        handle_configuration_error)    # noqa
    app.add_exception_handler(IngestionError,            handle_ingestion_error)        # noqa
    app.add_exception_handler(RetrievalError,            handle_retrieval_error)        # noqa
    # Base class last — catches anything not matched above
    app.add_exception_handler(EgyptianLawAssistantError, handle_domain_error)           # noqa