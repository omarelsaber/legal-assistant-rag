"""
Health and readiness check endpoints.

Two endpoints, distinct purposes:

  GET /health  — Liveness probe.
    "Is the process alive?"
    Returns 200 immediately. No I/O. Used by Docker HEALTHCHECK and
    Kubernetes liveness probes to decide whether to restart the container.
    Must never block or fail due to downstream dependencies.

  GET /ready   — Readiness probe.
    "Is the process ready to serve traffic?"
    Checks that ChromaDB is reachable and the vector collection is
    non-empty. Returns 503 if not ready. Used by Kubernetes readiness
    probes and load balancers to decide whether to route traffic here.
    A 503 from /ready does NOT restart the container — it just removes
    it from the load balancer rotation until it recovers.

Why separate endpoints?
  A container that is alive but not ready (e.g., still loading the index)
  should not receive traffic, but also should not be killed and restarted.
  Conflating the two probes causes either unnecessary restarts (if liveness
  is too strict) or traffic routing to broken instances (if readiness is
  too lenient).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.core.config import Settings
from src.api.dependencies import get_api_settings
from src.knowledge_base.vector_store import get_chroma_client, get_collection_name

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 immediately. No I/O. Confirms the process is alive.",
    response_description="Process is alive.",
)
async def health() -> dict[str, str]:
    """
    Liveness probe — always returns ``{"status": "ok"}`` if the process is running.

    This endpoint deliberately performs zero I/O. If it fails, the process
    itself is broken and a restart is warranted.
    """
    return {"status": "ok"}

@router.get(
    "/ready",
    summary="Readiness probe",
    description=(
        "Checks that ChromaDB is reachable and the vector collection is populated. "
        "Returns 503 if the index is not ready to serve queries."
    ),
    responses={
        200: {"description": "Service is ready to handle query requests."},
        503: {"description": "Service is not yet ready (index empty or ChromaDB unreachable)."},
    },
)
async def ready(
    settings: Settings = Depends(get_api_settings),
) -> JSONResponse:
    """
    Readiness probe — verifies ChromaDB connectivity and index population.

    Checks performed:
      1. ChromaDB client can be instantiated (connection to persist dir).
      2. The config-namespaced collection exists and contains at least
         one vector (i.e., ingestion has been run).

    Returns 200 if both checks pass, 503 otherwise. The 503 body includes
    a ``reason`` field so operators can distinguish "ChromaDB unreachable"
    from "index is empty — run make ingest".
    """
    collection_name = get_collection_name(settings)

    try:
        client = get_chroma_client()
        # list_collections() is a lightweight metadata call —
        # it does not load any vectors into memory.
        existing = [c.name for c in client.list_collections()]

        if collection_name not in existing:
            logger.warning(
                "Readiness check failed: collection %r not found. "
                "Run `make ingest` to populate the index.",
                collection_name,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "reason": (
                        f"Collection '{collection_name}' does not exist. "
                        "Run the ingestion pipeline first."
                    ),
                },
            )

        collection = client.get_collection(collection_name)
        vector_count = collection.count()

        if vector_count == 0:
            logger.warning(
                "Readiness check failed: collection %r is empty.",
                collection_name,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "reason": (
                        f"Collection '{collection_name}' exists but contains 0 vectors. "
                        "Run the ingestion pipeline to populate it."
                    ),
                },
            )

        logger.debug(
            "Readiness check passed: collection=%r  vectors=%d",
            collection_name,
            vector_count,
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "collection": collection_name,
                "vector_count": vector_count,
            },
        )

    except Exception as exc:
        logger.error("Readiness check failed with exception: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": f"ChromaDB connectivity check failed: {type(exc).__name__}: {exc}",
            },
        )