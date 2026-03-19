"""
LlamaIndex VectorStoreIndex builder for the Egyptian Law Assistant.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import Settings, get_settings
from src.core.exceptions import EmbeddingError, IngestionError
from src.core.schemas import DocumentChunk
from src.knowledge_base.embeddings import get_embedding_model
from src.knowledge_base.vector_store import get_collection_name, get_vector_store

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _chunk_to_text_node(chunk: DocumentChunk) -> TextNode:
    node_metadata: dict[str, str | int | float | bool] = {
        "source_file": chunk.source_file,
        "article_number": chunk.article_number or "",
        "character_count": len(chunk.content),
    }

    for key, value in chunk.metadata.items():
        if isinstance(value, (str, int, float, bool)):
            node_metadata[key] = value
        else:
            node_metadata[key] = str(value)

    return TextNode(
        id_=chunk.chunk_id,
        text=chunk.content,
        metadata=node_metadata,
    )


def build_index(
    chunks: list[DocumentChunk],
    settings: Settings | None = None,
) -> VectorStoreIndex:
    if not chunks:
        raise IngestionError(
            file_path="<in-memory>",
            reason="build_index() called with an empty chunks list."
        )

    active_settings = settings or get_settings()
    namespace_name = get_collection_name(active_settings)
    
    logger.info("Building index: %d chunks  namespace %r", len(chunks), namespace_name)

    nodes: list[TextNode] = [_chunk_to_text_node(chunk) for chunk in chunks]
    logger.info("Translated %d DocumentChunks  TextNodes", len(nodes))

    vector_store = get_vector_store(active_settings)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    embed_model = get_embedding_model(active_settings)

    try:
        index = VectorStoreIndex(
            nodes=[],
            storage_context=storage_context,
            embed_model=embed_model,
        )

        batch_size = 50
        total_batches = (len(nodes) + batch_size - 1) // batch_size
        logger.info(
            "Batching %d nodes into %d batches (size=%d) to respect Cohere rate limits.",
            len(nodes), total_batches, batch_size
        )

        @retry(
            wait=wait_exponential(multiplier=2, min=5, max=60),
            stop=stop_after_attempt(5),
            reraise=True
        )
        def _insert_batch_with_retry(batch_nodes: list[TextNode]) -> None:
            index.insert_nodes(batch_nodes)

        for i in range(0, len(nodes), batch_size):
            batch = nodes[i : i + batch_size]
            current_batch = (i // batch_size) + 1
            
            logger.info("Inserting batch %d/%d (%d nodes)...", current_batch, total_batches, len(batch))
            _insert_batch_with_retry(batch)
            
            if current_batch < total_batches:
                logger.info("Batch inserted. Sleeping 15 seconds to avoid HTTP 429...")
                time.sleep(15.0)

    except Exception as exc:
        raise EmbeddingError(
            model=active_settings.embedding_model,
            reason=f"VectorStoreIndex construction failed: {exc}",
        ) from exc

    logger.info("Index built and persisted to Pinecone (Namespace: %r).", namespace_name)
    return index


def load_index(settings: Settings | None = None) -> VectorStoreIndex:
    active_settings = settings or get_settings()

    vector_store = get_vector_store(active_settings)
    embed_model = get_embedding_model(active_settings)
    namespace_name = get_collection_name(active_settings)

    try:
        # Safe way to check Pinecone index stats
        stats = vector_store._pinecone_index.describe_index_stats()
        vector_count = stats.get('namespaces', {}).get(namespace_name, {}).get('vector_count', 0)
    except Exception:
        vector_count = -1

    if vector_count == 0:
        raise IngestionError(
            file_path="<pinecone>",
            reason=f"Namespace {namespace_name!r} exists but is empty. Run `make ingest`.",
        )

    logger.info("Loading index from Pinecone namespace %r (approx %d vectors)", namespace_name, vector_count)

    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        storage_context=storage_context,
        embed_model=embed_model,
    )

def main() -> None:
    pass

if __name__ == "__main__":
    main()
