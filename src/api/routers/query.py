"""
Query router for the Egyptian Law Assistant API.

Single responsibility: expose ``POST /query`` as a thin HTTP adapter over
``execute_query()`` from the query pipeline.

"Thin router" rule (enforced here):
  This file contains zero business logic. It does not:
    - Validate Arabic text content (done by Pydantic in QueryRequest)
    - Load indexes or manage ChromaDB connections (done by the pipeline)
    - Compute scores (done by the evaluation layer)
    - Catch domain exceptions (done by exception_handlers.py)

  It only: receives an HTTP request, extracts the validated body, calls
  the pipeline, and returns the serialised response.

Why no try/except here?
  Domain exceptions raised by ``execute_query()`` propagate up to FastAPI,
  which routes them to the registered exception handlers in
  ``exception_handlers.py``. Catching them here would duplicate that logic
  and undermine the centralised handler architecture.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from src.api.dependencies import get_api_settings
from src.core.config import Settings
from src.core.schemas import QueryRequest, QueryResponse
from src.query_engine.query_pipeline import execute_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])

@router.post(
    "",
    response_model=QueryResponse,
    summary="Query the Egyptian law corpus",
    description=(
        "Submit a natural language question in Arabic or English. "
        "Returns an LLM-generated answer grounded in the retrieved legal articles, "
        "along with the source article chunks used as context."
    ),
    responses={
        200: {"description": "Query answered successfully."},
        404: {"description": "No relevant articles found for the query."},
        422: {"description": "Request body failed validation (e.g., query too short)."},
        503: {"description": "LLM provider or embedding service is unavailable."},
    },
)
async def query_law(
    request: QueryRequest,
    settings: Settings = Depends(get_api_settings),
) -> QueryResponse:
    """
    Execute a RAG query against the Egyptian corporate law index.

    **Request body** (``QueryRequest``):
    - ``query``: Natural language question (Arabic or English, 3–2000 chars).
    - ``top_k``: Number of source chunks to retrieve (1–20, default 10).
    - ``filters``: Optional ChromaDB metadata filters
      (e.g. ``{"law_number": "159"}``).

    **Response** (``QueryResponse``):
    - ``answer``: LLM-generated answer grounded in retrieved articles.
    - ``source_chunks``: The retrieved ``DocumentChunk`` objects used as context.
      Each chunk includes ``article_number``, ``source_file``, and ``content``.
    - ``confidence_score``: Always ``null`` from this endpoint — populated
      only during evaluation runs via the Ragas evaluator.
    - ``llm_provider_used``: Which provider generated the answer
      (``"ollama"`` or ``"claude"``).

    **Example request**::

        POST /query
        {
          "query": "ما هي شروط تأسيس شركة المساهمة؟",
          "top_k": 10
        }

    **Domain exceptions → HTTP status mapping** (handled automatically):
    - ``EmptyRetrievalError`` → 404
    - ``LLMProviderError``    → 503
    - ``EmbeddingError``      → 503
    - ``ConfigurationError``  → 500
    """
    logger.info(
        "POST /query: query=%r  top_k=%d  provider=%r",
        request.query[:60],
        request.top_k,
        settings.llm_provider,
    )

    response = await execute_query(request=request, settings=settings)

    logger.info(
        "POST /query: answered  chunks_cited=%d  provider=%r",
        len(response.source_chunks),
        response.llm_provider_used,
    )

    return response
