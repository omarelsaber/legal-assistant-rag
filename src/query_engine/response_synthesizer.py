"""
LlamaIndex → domain schema translation for the Egyptian Law Assistant.

Responsibilities:
  - Accept a raw LlamaIndex ``Response`` object and translate it into our
    ``QueryResponse`` domain type.
  - Reconstruct ``DocumentChunk`` objects from ``NodeWithScore`` metadata
    stored in ChromaDB during Sprint 3 ingestion.

Architectural contract (the key boundary rule):
  This is the LAST file in the pipeline that may reference LlamaIndex types.
  Everything returned from ``map_response()`` is a pure Pydantic domain object.
  The ``api/`` layer, ``evaluation/`` context, and any external caller receive
  only ``QueryResponse`` — never a LlamaIndex ``Response`` or ``NodeWithScore``.

Metadata contract (depends on Sprint 3 indexer.py):
  The metadata keys written by ``_chunk_to_text_node()`` in indexer.py are:
    - "source_file"        → str   (filename, e.g. "corporate_law.txt")
    - "article_number"     → str   (e.g. "مادة 1", empty string if absent)
    - "chunk_index"        → int   (position in source document)
    - "raw_article_number" → str   (e.g. "1")
    - "character_count"    → int   (length of content)
    - "source_path"        → str   (absolute path, if set)
  Any of these may be absent if the chunk was ingested by a different version
  of the pipeline — all lookups use ``.get()`` with safe defaults.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.exceptions import RetrievalError
from src.core.schemas import DocumentChunk, QueryResponse

logger = logging.getLogger(__name__)

# ── Node → DocumentChunk translation ──────────────────────────────────────────

def _node_with_score_to_chunk(node_with_score: Any) -> DocumentChunk:
    """
    Translate a single LlamaIndex ``NodeWithScore`` into a ``DocumentChunk``.

    We type ``node_with_score`` as ``Any`` intentionally: importing
    ``NodeWithScore`` from LlamaIndex here would create a hard dependency
    on LlamaIndex internals in a module that is otherwise pure domain code.
    The duck-typed access pattern is explicit and safe — if LlamaIndex ever
    renames these attributes, the failure is immediate and obvious.

    Attribute access map:
      node_with_score.node.id_          → DocumentChunk.chunk_id
      node_with_score.node.text         → DocumentChunk.content
      node_with_score.node.metadata     → used to populate remaining fields
      node_with_score.score             → stored in metadata["similarity_score"]

    Args:
        node_with_score: A LlamaIndex ``NodeWithScore`` from a retrieval result.

    Returns:
        A ``DocumentChunk`` populated from the node's text and metadata.
    """
    node     = node_with_score.node
    score    = node_with_score.score      # float similarity score, may be None
    metadata = node.metadata or {}

    # Pull the fields we explicitly set in indexer._chunk_to_text_node()
    source_file    = metadata.get("source_file", "unknown")
    article_number = metadata.get("article_number") or None  # "" → None

    # Reconstruct the full metadata dict for the domain object.
    # Include the similarity score so callers (evaluation, API) can surface it.
    chunk_metadata: dict[str, Any] = {
        **metadata,
        "similarity_score": round(score, 6) if score is not None else None,
    }

    return DocumentChunk(
        chunk_id=node.id_,
        source_file=source_file,
        article_number=article_number,
        content=node.text,
        metadata=chunk_metadata,
    )


# ── Main public interface ──────────────────────────────────────────────────────

def map_response(
    llama_response: Any,
    provider: str,
) -> QueryResponse:
    """
    Translate a LlamaIndex ``Response`` into a ``QueryResponse`` domain object.

    This function is the boundary gate between LlamaIndex internals and the
    rest of the application. After this call, no LlamaIndex type exists in
    the returned value.

    Handles three edge cases explicitly:
      1. Empty answer string  — LLM returned nothing; wrapped as a graceful
         "no answer found" message rather than an empty string, which would
         confuse API clients.
      2. No source nodes      — retrieval succeeded but LLM produced an
         answer with no grounding. Logged as a warning (potential hallucination
         risk in a legal context).
      3. Node translation failure — a single malformed node is skipped and
         logged rather than failing the entire response, since the answer
         itself is still valid.

    Args:
        llama_response: A LlamaIndex ``Response`` (or ``StreamingResponse``)
                        object returned by ``query_engine.query()`` or
                        ``await query_engine.aquery()``.
        provider:       The LLM provider identifier used for this query
                        (e.g. ``"ollama"`` or ``"claude"``). Stored in the
                        response for observability and evaluation tracking.

    Returns:
        A fully-populated ``QueryResponse`` domain object.

    Raises:
        RetrievalError: If ``llama_response`` is ``None`` or lacks a
                        ``.response`` attribute — indicates a pipeline
                        misconfiguration rather than a normal empty result.
    """
    # ── Guard: None response means pipeline misconfiguration ─────────────────
    if llama_response is None:
        raise RetrievalError(
            "LlamaIndex query engine returned None. "
            "This indicates a misconfiguration — ensure the index is loaded "
            "and the LLM provider is reachable."
        )

    raw_answer: str | None = getattr(llama_response, "response", None)

    if raw_answer is None:
        raise RetrievalError(
            "LlamaIndex Response object has no 'response' attribute. "
            f"Got type: {type(llama_response).__name__}. "
            "Ensure query_engine.query() / aquery() is returning a Response object."
        )

    # ── Handle empty answer gracefully ────────────────────────────────────────
    answer = raw_answer.strip()
    if not answer:
        logger.warning(
            "LLM returned an empty answer for provider=%r. "
            "Substituting a 'no answer found' message.",
            provider,
        )
        answer = (
            "لم يتم العثور على إجابة كافية في المستندات المتاحة. "
            "يرجى إعادة صياغة السؤال أو التحقق من اكتمال قاعدة البيانات."
        )  # "No sufficient answer found in the available documents."

    # ── Translate source nodes ────────────────────────────────────────────────
    raw_source_nodes: list[Any] = getattr(llama_response, "source_nodes", []) or []

    if not raw_source_nodes:
        logger.warning(
            "Response has no source nodes (provider=%r). "
            "Answer may be ungrounded — review for hallucination risk in legal context.",
            provider,
        )

    source_chunks: list[DocumentChunk] = []
    for node_with_score in raw_source_nodes:
        try:
            chunk = _node_with_score_to_chunk(node_with_score)
            source_chunks.append(chunk)
        except Exception as exc:
            # One malformed node should not kill an otherwise valid response.
            # Log it explicitly so it surfaces in monitoring.
            logger.error(
                "Failed to translate NodeWithScore to DocumentChunk: %s — skipping node.",
                exc,
            )

    logger.debug(
        "Mapped response: answer_len=%d, source_chunks=%d, provider=%r",
        len(answer),
        len(source_chunks),
        provider,
    )

    return QueryResponse(
        answer=answer,
        source_chunks=source_chunks,
        confidence_score=None,   # Populated by evaluation/ragas_evaluator.py, not here
        llm_provider_used=provider,
    )