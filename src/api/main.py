"""
FastAPI application factory for the Egyptian Law Assistant.

This module is the composition root of the API layer. It:
  1. Creates the FastAPI ``app`` instance.
  2. Configures ``CORSMiddleware`` for React frontend access.
  3. Registers all domain exception handlers.
  4. Includes all routers with their prefixes.
  5. Configures structured logging at startup.
  6. Provides a ``lifespan`` context manager for startup/shutdown hooks.

What this module does NOT do:
  - Contain any business logic (routers and pipeline own that).
  - Import LlamaIndex, ChromaDB, or Ragas directly.
  - Know about specific domain exceptions (exception_handlers.py owns that).

Running the server:
  Development  : python -m src.api.main
  Production   : uvicorn src.api.main:app --host 0.0.0.0 --port 8080
  Docker       : CMD in services/query/Dockerfile calls uvicorn directly.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.exception_handlers import register_exception_handlers
from src.api.routers import health, query
from src.core.config import get_settings

# ── Project root on sys.path (for direct script execution) ────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ── Logging configuration ──────────────────────────────────────────────────────

def _configure_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the API process.

    Uses the standard library ``logging`` module. In production, replace
    the ``StreamHandler`` with a JSON formatter (e.g., ``python-json-logger``)
    so log aggregators (Datadog, CloudWatch) can parse fields structurally.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR. Read from Settings.
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Override any pre-existing root logger config
    )

    # Suppress noisy third-party loggers at INFO level
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("llama_index").setLevel(logging.WARNING)

# ── Application lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager — runs startup logic before the first
    request and shutdown logic after the last.

    Startup:
      - Log the active configuration (provider, model, collection name).
      - Future: pre-warm the ChromaDB connection and LlamaIndex index so
        the first query is not slow. (Not done here to keep the API
        container stateless — the query pipeline lazy-loads on first request.)

    Shutdown:
      - Log that the server is stopping.
      - Future: flush any pending MLflow runs, close connection pools.
    """
    settings = get_settings()
    _configure_logging(settings.log_level)

    logger.info("=" * 60)
    logger.info("Egyptian Law Assistant API — Starting")
    logger.info("  LLM provider   : %s", settings.llm_provider)
    logger.info("  LLM model      : %s", settings.ollama_model)
    logger.info("  Embedding model: %s", settings.embedding_model)
    logger.info("  Chunk size     : %d / overlap %d", settings.chunk_size, settings.chunk_overlap)
    logger.info("  ChromaDB       : %s:%d", settings.chroma_host, settings.chroma_port)
    logger.info("  MLflow URI     : %s", settings.mlflow_tracking_uri)
    logger.info("=" * 60)

    yield  # ← server is live and handling requests between startup and shutdown

    logger.info("Egyptian Law Assistant API — Shutting down")

# ── Application factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """
    Construct and configure the FastAPI application instance.

    Separated into a factory function (rather than module-level ``app = FastAPI()``)
    so tests can call ``create_app()`` to get a fresh instance with
    ``dependency_overrides`` applied, without sharing state with other tests.

    Returns:
        A fully configured ``FastAPI`` instance ready to be served.
    """
    settings = get_settings()

    app = FastAPI(
        title="Egyptian Corporate Law Assistant",
        description=(
            "A production-grade RAG API for querying Egyptian corporate law. "
            "Backed by LlamaIndex, ChromaDB, and local Ollama LLMs."
        ),
        version="0.1.0",
        docs_url="/docs",       # Swagger UI
        redoc_url="/redoc",     # ReDoc UI
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS — allow React frontend on any origin ──────────────────────────────

    # ``allow_origins=["*"]`` permits requests from any domain.
    # For production, replace "*" with your frontend's specific origin:
    #   allow_origins=["https://your-frontend.com"]
    #
    # ``allow_methods=["*"]`` and ``allow_headers=["*"]`` are required for
    # React's fetch() to send JSON bodies (Content-Type: application/json
    # triggers a CORS preflight OPTIONS request — without these, the
    # preflight returns 400 and the actual request is never sent).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for local development
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers — most specific subclass first ─────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    # All routes are prefixed with /api/v1 for future versioning.
    # The React frontend calls: POST http://localhost:8080/api/v1/query
    API_PREFIX = "/api/v1"
    app.include_router(health.router,     prefix=API_PREFIX)
    app.include_router(query.router,      prefix=API_PREFIX)

    logger.debug("FastAPI app created with %d routes", len(app.routes))
    return app

# ── Module-level app instance ──────────────────────────────────────────────────
# This is what uvicorn imports: ``uvicorn src.api.main:app``
# Tests that need isolation should call create_app() directly.
app: FastAPI = create_app()

# ── Development entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    _settings = get_settings()
    _configure_logging(_settings.log_level)

    logger.info(
        "Starting development server on http://%s:%d",
        _settings.api_host,
        _settings.api_port,
    )
    logger.info("Swagger UI: http://%s:%d/docs", _settings.api_host, _settings.api_port)

    uvicorn.run(
        "src.api.main:app",
        host=_settings.api_host,
        port=_settings.api_port,
        reload=_settings.api_reload,  # True only in local dev (set API_RELOAD=true in .env)
        log_level=_settings.log_level.lower(),
    )
