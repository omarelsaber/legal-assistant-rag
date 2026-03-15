"""
Retriever configuration for the Egyptian Law Assistant.

Responsibilities:
  - Accept a ``VectorStoreIndex`` (produced by ``knowledge_base/indexer.py``)
    and return a configured LlamaIndex retriever.
  - This is the single place in the codebase that sets retrieval strategy
    (vector similarity, top_k, optional metadata filters).

What this module does NOT do:
  - Build or persist the index           — that is indexer.py.
  - Generate answers                     — that is query_pipeline.py.
  - Translate results to domain types    — that is response_synthesizer.py.

Architectural boundary:
  ``VectorStoreIndex`` and ``VectorIndexRetriever`` are LlamaIndex-internal
  types. They are allowed within ``query_engine/`` but must never cross into
  ``api/``. The synthesizer translates them to domain types before the API
  layer ever sees a result.
"""

from __future__ import annotations

import logging

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import VectorIndexRetriever

logger = logging.getLogger(__name__)


def get_retriever(
    index: VectorStoreIndex,
    top_k: int = 5,
) -> VectorIndexRetriever:
    """
    Build a ``VectorIndexRetriever`` from an existing ``VectorStoreIndex``.

    The retriever performs approximate nearest-neighbour search in the
    ChromaDB collection using cosine similarity (set at collection creation
    in ``vector_store.py``). On each query it:
      1. Embeds the query string using the same embedding model as ingestion.
      2. Queries ChromaDB for the ``top_k`` closest vectors.
      3. Returns ``NodeWithScore`` objects containing the chunk text,
         metadata, and similarity score.

    Args:
        index: A ``VectorStoreIndex`` loaded via ``knowledge_base.indexer.load_index()``.
               The index must already be populated — see ``indexer.build_index()``.
        top_k: Number of most-similar document chunks to retrieve per query.
               Bounded to [1, 20] by the ``QueryRequest`` schema; the default
               of 5 balances context richness against LLM context-window cost.

    Returns:
        A configured ``VectorIndexRetriever`` ready to be passed to a
        ``RetrieverQueryEngine``.

    Raises:
        ValueError: If ``top_k`` is less than 1. (Upstream validation in
                    ``QueryRequest`` should prevent this, but we guard here
                    defensively since ``get_retriever`` can be called directly
                    in tests and evaluation scripts.)

    Example::

        index     = load_index(settings)
        retriever = get_retriever(index, top_k=request.top_k)
        engine    = RetrieverQueryEngine.from_args(retriever=retriever, llm=llm)
    """
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}.")

    logger.debug("Configuring VectorIndexRetriever with top_k=%d", top_k)

    retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=top_k,
    )

    return retriever