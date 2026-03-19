"""
Pinecone vector store interface for the Egyptian Law Assistant.
"""

from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache

from pinecone import Pinecone
from llama_index.vector_stores.pinecone import PineconeVectorStore

from src.core.config import Settings

logger = logging.getLogger(__name__)

# اسم الـ Index اللي إنت أنشأته على موقع Pinecone
PINECONE_INDEX_NAME = "egyptian-law"

def get_collection_name(settings: Settings) -> str:
    """
    Derive a deterministic Namespace name from the active config.
    We use Pinecone Namespaces to isolate different embedding experiments.
    """
    config_fingerprint = (
        f"{settings.embedding_model}"
        f"|{settings.chunk_size}"
        f"|{settings.chunk_overlap}"
    )
    config_hash = hashlib.md5(config_fingerprint.encode("utf-8")).hexdigest()[:8]
    namespace_name = f"egyptian_law_{config_hash}"

    logger.debug(
        "Namespace derived: %s  (fingerprint: %r)",
        namespace_name,
        config_fingerprint,
    )
    return namespace_name


def get_pinecone_client() -> Pinecone:
    """
    Return a Pinecone Client using the API key from environment variables.
    """
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY is not set in environment variables.")
    
    logger.info("Initialising Pinecone Client")
    return Pinecone(api_key=api_key)


def get_vector_store(settings: Settings) -> PineconeVectorStore:
    """
    Build and return a LlamaIndex ``PineconeVectorStore`` for the active config.
    """
    namespace = get_collection_name(settings)
    
    # compute simple metadata tuple and delegate to cached helper
    metadata = (
        settings.embedding_model,
        settings.chunk_size,
        settings.chunk_overlap,
    )
    return _get_vector_store_cached(namespace, metadata)


@lru_cache(maxsize=1)
def _get_vector_store_cached(
    namespace: str,
    metadata: tuple[str, int, int],
) -> PineconeVectorStore:
    """Internal helper cached by namespace and model metadata."""
    embedding_model, chunk_size, chunk_overlap = metadata

    pc = get_pinecone_client()
    
    logger.info(
        "Connecting to Pinecone index: %r | Namespace: %r (embedding_model=%r, chunk_size=%d, overlap=%d)",
        PINECONE_INDEX_NAME,
        namespace,
        embedding_model,
        chunk_size,
        chunk_overlap,
    )

    pinecone_index = pc.Index(PINECONE_INDEX_NAME)

    return PineconeVectorStore(
        pinecone_index=pinecone_index,
        namespace=namespace
    )
