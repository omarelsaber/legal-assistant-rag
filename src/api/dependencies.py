"""
FastAPI dependency injection for the Egyptian Law Assistant API.

Dependency functions in this module are passed to FastAPI's ``Depends()``
mechanism. FastAPI calls them automatically before each request handler,
injects the return value as a parameter, and handles caching/scoping.

Architectural role:
  Dependencies are the seam between FastAPI's request lifecycle and our
  domain layer. They translate "HTTP request context" (headers, auth tokens,
  query params) into typed domain objects that route handlers use.

  Route handlers should never call ``get_settings()`` or construct domain
  objects directly — they receive them via Depends. This keeps handlers
  testable: override a dependency in tests with ``app.dependency_overrides``
  and the handler never knows the difference.

Current dependencies:
  get_api_settings() — returns the validated Settings singleton.

Future dependencies to add here (not in scope for Sprint 6):
  get_current_user()  — JWT/API-key authentication.
  get_rate_limiter()  — per-client request throttling.
  require_index_ready() — readiness guard: raises 503 if ChromaDB is empty.
"""

from __future__ import annotations

from src.core.config import Settings, get_settings

def get_api_settings() -> Settings:
    """
    FastAPI dependency that returns the validated ``Settings`` singleton.

    Wrapping ``get_settings()`` in a dependency function (rather than
    importing ``settings`` directly in route handlers) enables two things:

      1. Test overrides via ``app.dependency_overrides[get_api_settings]``.
         Tests can inject a custom ``Settings`` instance with a different
         LLM provider, chunk size, or ChromaDB path without touching the
         global singleton or environment variables.

      2. Future authentication: if settings ever become per-request
         (e.g., per-tenant API keys), this function is the single place
         to add that logic.

    Returns:
        The active ``Settings`` singleton — validated at process startup,
        cached for the process lifetime.

    Example (in a route handler)::

        @router.post("/query")
        async def query(
            request: QueryRequest,
            settings: Settings = Depends(get_api_settings),
        ) -> QueryResponse:
            return await execute_query(request, settings)

    Example (in a test)::

        app.dependency_overrides[get_api_settings] = lambda: Settings(
            llm_provider="ollama",
            chunk_size=256,
        )
    """
    return get_settings()