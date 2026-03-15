"""

ChromaDB vector store interface for the Egyptian Law Assistant.



Responsibilities:

  - Derive a deterministic, experiment-safe ChromaDB collection name from

    the active settings (Performance Decision #2: config-hash namespacing).

  - Initialise a ChromaDB PersistentClient (local MVP; swap host/port for

    production by changing the client constructor only  no callers change).

  - Expose a LlamaIndex ChromaVectorStore wrapping that collection.



What this module does NOT do:

  - Build or query indexes   that is indexer.py's responsibility.

  - Embed text              that is embeddings.py's responsibility.

  - Know about DocumentChunk or any domain schema.



Architectural note (Architecture Decision #2  Domain-Driven):

  All ChromaDB-specific types are contained here. The rest of the codebase

  imports only `get_vector_store()` and never touches chromadb directly.

"""



from __future__ import annotations



import hashlib

import logging

from functools import lru_cache

from pathlib import Path



import chromadb

from llama_index.vector_stores.chroma import ChromaVectorStore



from src.core.config import Settings



logger = logging.getLogger(__name__)



# Default local persistence directory (relative to project root).

# Overridable via the settings object so tests can redirect to a tmp dir.

_DEFAULT_CHROMA_PATH = "./chroma_db"





#  Collection Naming 



def get_collection_name(settings: Settings) -> str:

    """

    Derive a deterministic ChromaDB collection name from the active config.



    Why hashing instead of a plain name?

    Each unique combination of (embedding_model, chunk_size, chunk_overlap)

    produces a different vector space. Mixing vectors from different configs

    in the same collection causes silent retrieval degradation. By encoding

    the config into the collection name we get:



      - Automatic isolation: experiments never overwrite each other.

      - Reproducibility: the same config always resolves to the same collection.

      - MLflow alignment: log `collection_name` as a run param and you have a

        direct link between an experiment run and its underlying vector data.



    The hash is truncated to 8 hex chars (4 bytes = 4 billion combinations),

    which is more than sufficient for the number of distinct configs in practice.



    Args:

        settings: The active Settings singleton.



    Returns:

        A string of the form ``"egyptian_law_{8-char-hex}"``,

        e.g. ``"egyptian_law_a3f9c1b2"``.



    Example::



        # chunk_size=512, chunk_overlap=50, embedding_model=nomic-embed-text

        >>> get_collection_name(settings)

        'egyptian_law_3d8f2a11'

    """

    config_fingerprint = (

        f"{settings.embedding_model}"

        f"|{settings.chunk_size}"

        f"|{settings.chunk_overlap}"

    )

    config_hash = hashlib.md5(config_fingerprint.encode("utf-8")).hexdigest()[:8]

    collection_name = f"egyptian_law_{config_hash}"



    logger.debug(

        "Collection name derived: %s  (fingerprint: %r)",

        collection_name,

        config_fingerprint,

    )

    return collection_name





#  ChromaDB Client 



def get_chroma_client(persist_dir: str = _DEFAULT_CHROMA_PATH) -> chromadb.PersistentClient:

    """

    Return a ChromaDB PersistentClient writing to ``persist_dir``.



    For the local MVP we use ``PersistentClient`` (data survives process

    restarts). In a multi-container deployment, replace this with

    ``chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)``

     no callers need to change because they only see ``get_vector_store()``.



    Args:

        persist_dir: Local filesystem path for ChromaDB to store its data.

                     Created automatically if it does not exist.



    Returns:

        A configured ``chromadb.PersistentClient`` instance.

    """

    Path(persist_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Initialising ChromaDB PersistentClient at: %s", persist_dir)

    return chromadb.PersistentClient(path=persist_dir)





#  LlamaIndex Vector Store 



def get_vector_store(

    settings: Settings,

    persist_dir: str = _DEFAULT_CHROMA_PATH,

) -> ChromaVectorStore:

    """

    Build and return a LlamaIndex ``ChromaVectorStore`` for the active config.



    The result is cached by (settings identity, persist_dir) so repeated

    calls within the same process reuse the same store without re-opening

    the ChromaDB client. Call ``get_vector_store.cache_clear()`` in tests

    that need a fresh store.



    The ChromaDB collection is created if it does not exist, or opened if it

    does (``get_or_create_collection``). This makes the function safe to call

    on first run (creates) and on subsequent runs (resumes).



    Args:

        settings:    The active Settings singleton.

        persist_dir: Filesystem path for ChromaDB persistence.



    Returns:

        A ``ChromaVectorStore`` backed by the config-namespaced collection.



    Raises:

        chromadb.errors.InvalidDimensionException: If the collection exists

            with a different embedding dimension than the current config.

            This is surfaced as-is; the caller (indexer.py) wraps it in

            an ``EmbeddingError``.

    """

    collection_name = get_collection_name(settings)

    # compute simple metadata tuple and delegate to cached helper
    metadata = (
        settings.embedding_model,
        settings.chunk_size,
        settings.chunk_overlap,
    )
    return _get_vector_store_cached(collection_name, persist_dir, metadata)


def _get_vector_store_cached(

    collection_name: str,

    persist_dir: str,

    metadata: tuple[str, int, int],

) -> ChromaVectorStore:
    """Internal helper cached by collection name, persist_dir, and model metadata.

    ``metadata`` is a tuple containing (embedding_model, chunk_size,
    chunk_overlap); all elements are primitives and thus hashable.
    """

    embedding_model, chunk_size, chunk_overlap = metadata

    client = get_chroma_client(persist_dir)

    logger.info(
        "Opening ChromaDB collection: %r  (embedding_model=%r, chunk_size=%d, overlap=%d)",
        collection_name,
        embedding_model,
        chunk_size,
        chunk_overlap,
    )

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "embedding_model": embedding_model,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "hnsw:space": "cosine",   # cosine similarity for semantic search
        },
    )

    logger.info(
        "Collection ready. Existing vectors: %d",
        collection.count(),
    )

    return ChromaVectorStore(chroma_collection=collection)
