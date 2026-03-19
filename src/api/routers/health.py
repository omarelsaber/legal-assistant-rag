"""
Health and readiness check endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.core.config import Settings
from src.api.dependencies import get_api_settings
from src.knowledge_base.vector_store import get_vector_store, get_collection_name

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 immediately. No I/O. Confirms the process is alive.",
    response_description="Process is alive.",
)
async def health() -> dict[str, str]:
    return {"status": "ok"}

@router.get(
    "/ready",
    summary="Readiness probe",
    description=(
        "Checks that Pinecone is reachable and the vector namespace is populated. "
        "Returns 503 if the index is not ready to serve queries."
    ),
    responses={
        200: {"description": "Service is ready to handle query requests."},
        503: {"description": "Service is not yet ready (index empty or Pinecone unreachable)."},
    },
)
async def ready(
    settings: Settings = Depends(get_api_settings),
) -> JSONResponse:
    namespace_name = get_collection_name(settings)

    try:
        vector_store = get_vector_store(settings)
        # Safe way to query Pinecone stats
        stats = vector_store._pinecone_index.describe_index_stats()
        
        namespaces = stats.get('namespaces', {})
        if namespace_name not in namespaces:
             logger.warning(
                 "Readiness check failed: namespace %r not found. "
                 "Run `make ingest` to populate the index.",
                 namespace_name,
             )
             return JSONResponse(
                 status_code=503,
                 content={
                     "status": "not_ready",
                     "reason": (
                         f"Namespace '{namespace_name}' does not exist in Pinecone. "
                         "Run the ingestion pipeline first."
                     ),
                 },
             )

        vector_count = namespaces.get(namespace_name, {}).get('vector_count', 0)

        if vector_count == 0:
            logger.warning(
                "Readiness check failed: namespace %r is empty.",
                namespace_name,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "reason": (
                        f"Namespace '{namespace_name}' exists but contains 0 vectors. "
                        "Run the ingestion pipeline to populate it."
                    ),
                },
            )

        logger.debug(
            "Readiness check passed: namespace=%r  vectors=%d",
            namespace_name,
            vector_count,
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "namespace": namespace_name,
                "vector_count": vector_count,
            },
        )

    except Exception as exc:
        logger.error("Readiness check failed with exception: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": f"Pinecone connectivity check failed: {type(exc).__name__}: {exc}",
            },
        )