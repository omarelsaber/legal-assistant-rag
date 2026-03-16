"""

LlamaIndex VectorStoreIndex builder for the Egyptian Law Assistant.



Responsibilities:

  - Convert ``DocumentChunk`` domain objects into LlamaIndex ``TextNode`` objects.

    This is the single translation point between the domain schema and the

    LlamaIndex data model  LlamaIndex types never leak past this file.

  - Tie together ``get_vector_store()`` and ``get_embedding_model()`` to build

    and persist a ``VectorStoreIndex`` in ChromaDB.

  - Provide a ``load_index()`` function for the query service to load an

    existing index without re-embedding.



Data flow:

  DocumentChunk (domain)

        _chunk_to_text_node()           boundary translation (this file)

  TextNode (LlamaIndex internal)

        VectorStoreIndex.from_documents()

  ChromaVectorStore (persisted)

        load_index() on query startup

  VectorStoreIndex (ready for querying)



Architectural note:

  ``build_index()`` and ``load_index()`` return a ``VectorStoreIndex``.

  This LlamaIndex type IS allowed to cross into ``query_engine/`` because

  the query engine is the next bounded context in the pipeline. However,

  the ``VectorStoreIndex`` must never reach the ``api/`` layer  the

  ``response_synthesizer.py`` translates it back to domain types first.

"""



from __future__ import annotations



import json
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



#  Project root  needed for the main() CLI block 

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(_PROJECT_ROOT) not in sys.path:

    sys.path.insert(0, str(_PROJECT_ROOT))





#  Domain  LlamaIndex Translation 



def _chunk_to_text_node(chunk: DocumentChunk) -> TextNode:

    """

    Translate a single ``DocumentChunk`` domain object into a LlamaIndex ``TextNode``.



    Mapping decisions:

      - ``chunk.chunk_id``        ``TextNode.id_``

        Using our deterministic hash ID (not a new uuid4) means ChromaDB

        upserts are idempotent: re-indexing the same chunk updates it in

        place rather than creating a duplicate vector.



      - ``chunk.content``         ``TextNode.text``

        The raw article text that will be embedded and searched.



      - ``chunk.article_number``  stored in ``TextNode.metadata``

        LlamaIndex surfaces metadata fields in retrieved ``NodeWithScore``

        objects, making citation extraction straightforward in the query engine.



      - ``chunk.source_file``     stored in ``TextNode.metadata``

        Required for provenance  users need to know which law document

        an answer was drawn from.



      - ``chunk.metadata``        merged into ``TextNode.metadata``

        Preserves chunk_index, character_count, and any future fields

        added to the ingestion pipeline without requiring changes here.



    Args:

        chunk: A validated ``DocumentChunk`` from the ingestion pipeline.



    Returns:

        A ``TextNode`` ready for embedding and insertion into ChromaDB.

    """

    # Build a flat metadata dict  ChromaDB requires scalar values only

    # (str, int, float, bool). No nested dicts or lists.

    node_metadata: dict[str, str | int | float | bool] = {

        "source_file": chunk.source_file,

        "article_number": chunk.article_number or "",

        "character_count": len(chunk.content),

    }



    # Merge ingestion-pipeline metadata, filtering out any non-scalar values

    # defensively (e.g. if a future ingestion step adds a list field).

    for key, value in chunk.metadata.items():

        if isinstance(value, (str, int, float, bool)):

            node_metadata[key] = value

        else:

            # Convert complex values to string so no metadata is silently lost

            node_metadata[key] = str(value)



    return TextNode(

        id_=chunk.chunk_id,      # deterministic ID  idempotent upserts

        text=chunk.content,

        metadata=node_metadata,

    )





#  Index Builder 



def build_index(

    chunks: list[DocumentChunk],

    settings: Settings | None = None,

    persist_dir: str = "./chroma_db",

) -> VectorStoreIndex:

    """

    Convert ``DocumentChunk`` objects into a persisted ``VectorStoreIndex``.



    Steps:

      1. Translate each ``DocumentChunk`` to a LlamaIndex ``TextNode``.

      2. Obtain the config-namespaced ``ChromaVectorStore``.

      3. Build a ``StorageContext`` wiring the store to LlamaIndex.

      4. Call ``VectorStoreIndex`` with the nodes  LlamaIndex embeds each

         node's text and writes the vector + metadata to ChromaDB.

      5. Return the index for immediate querying (the query service can also

         reload it later via ``load_index()`` without re-embedding).



    Args:

        chunks:      List of ``DocumentChunk`` objects from the ingestion pipeline.

                     Must be non-empty.

        settings:    Active settings (defaults to the global singleton).

                     Pass an override instance in tests.

        persist_dir: ChromaDB persistence directory.



    Returns:

        A ``VectorStoreIndex`` backed by the persisted ChromaDB collection.



    Raises:

        IngestionError:  If ``chunks`` is empty  nothing to index.

        EmbeddingError:  If the Ollama embedding server is unreachable or

                         returns a dimension that conflicts with the collection.

    """

    if not chunks:

        raise IngestionError(

            file_path="<in-memory>",

            reason="build_index() called with an empty chunks list. "

                   "Run the ingestion pipeline first.",

        )



    active_settings = settings or get_settings()



    collection_name = get_collection_name(active_settings)

    logger.info(

        "Building index: %d chunks  collection %r",

        len(chunks),

        collection_name,

    )



    #  Step 1: Translate domain objects to LlamaIndex nodes 

    nodes: list[TextNode] = [_chunk_to_text_node(chunk) for chunk in chunks]

    logger.info("Translated %d DocumentChunks  TextNodes", len(nodes))



    #  Step 2 & 3: Wire vector store into a StorageContext 

    vector_store = get_vector_store(active_settings, persist_dir)

    storage_context = StorageContext.from_defaults(vector_store=vector_store)



    #  Step 4: Embed and persist 
    embed_model = get_embedding_model(active_settings)

    try:
        # Initialize an empty index with the storage context
        index = VectorStoreIndex(
            nodes=[],
            storage_context=storage_context,
            embed_model=embed_model,
        )

        # Cohere free tier: 100,000 tokens per minute.
        # We chunk into batches of 50 to stay under the limit safely.
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
            # LlamaIndex will automatically embed the text of these nodes
            index.insert_nodes(batch_nodes)

        for i in range(0, len(nodes), batch_size):
            batch = nodes[i : i + batch_size]
            current_batch = (i // batch_size) + 1
            
            logger.info("Inserting batch %d/%d (%d nodes)...", current_batch, total_batches, len(batch))
            _insert_batch_with_retry(batch)
            
            # If not the last batch, sleep to cool off the token bucket
            if current_batch < total_batches:
                logger.info("Batch inserted. Sleeping 15 seconds to avoid HTTP 429...")
                time.sleep(15.0)

    except Exception as exc:
        # Wrap any LlamaIndex / Ollama / ChromaDB exception into our domain type
        # so callers get a typed exception with a clear message, not a raw
        # llama_index.core.exceptions.EmbeddingModelError stack trace.
        raise EmbeddingError(
            model=active_settings.embedding_model,
            reason=(
                f"VectorStoreIndex construction failed: {exc}. "
                "Ensure Ollama is running (if local) and the model is pulled."
            ),
        ) from exc



    logger.info(

        "Index built and persisted. Collection %r now contains %d vectors.",

        collection_name,

        vector_store.client.count(),   # type: ignore[attr-defined]

    )

    return index





#  Index Loader 



def load_index(

    settings: Settings | None = None,

    persist_dir: str = "./chroma_db",

) -> VectorStoreIndex:

    """

    Load an existing ``VectorStoreIndex`` from ChromaDB without re-embedding.



    Used by the query API at startup: the ingestion worker has already

    populated ChromaDB, so the query service just reconnects to the

    persisted collection.



    Args:

        settings:    Active settings. Defaults to the global singleton.

        persist_dir: ChromaDB persistence directory (must match the directory

                     used in ``build_index()``). Defaults to "./chroma_db".



    Returns:

        A ``VectorStoreIndex`` ready for querying.



    Raises:

        IngestionError: If the collection is empty  likely means ``build_index()``

                        has not been run yet for this config.

        EmbeddingError: If the embedding model cannot be loaded.

    """

    active_settings = settings or get_settings()



    vector_store = get_vector_store(active_settings, persist_dir)

    embed_model = get_embedding_model(active_settings)



    # Verify the collection is non-empty before returning an index that will

    # silently return zero results on every query.

    try:

        vector_count = vector_store.client.count()  # type: ignore[attr-defined]

    except Exception:

        vector_count = -1   # ChromaDB client may not expose .count()  be safe



    if vector_count == 0:

        collection_name = get_collection_name(active_settings)

        raise IngestionError(

            file_path="<chromadb>",

            reason=(

                f"Collection {collection_name!r} exists but is empty. "

                "Run `make ingest` to populate it before starting the query API."

            ),

        )



    logger.info(

        "Loading index from collection %r (%d vectors)",

        get_collection_name(active_settings),

        vector_count,

    )



    storage_context = StorageContext.from_defaults(vector_store=vector_store)



    return VectorStoreIndex.from_vector_store(

        vector_store=vector_store,

        storage_context=storage_context,

        embed_model=embed_model,

    )





#  CLI / Inspection Entry Point 



def main() -> None:

    """

    Development entry point: load Sprint 2's chunks.json and build the index.



    Reads  : data/processed/chunks.json  (produced by ingestion_pipeline.py)

    Writes : ./chroma_db/                (ChromaDB persistent store)



    Run with:

        python -m src.knowledge_base.indexer



    Prerequisites:

        1. Ollama must be running: ``ollama serve``

        2. Embedding model must be pulled: ``ollama pull nomic-embed-text``

        3. Sprint 2 must have been run: ``python -m src.document_processing.ingestion_pipeline``

    """

    import logging as _logging



    _logging.basicConfig(

        level=_logging.INFO,

        format="%(asctime)s [%(levelname)s] %(name)s  %(message)s",

        datefmt="%H:%M:%S",

    )



    chunks_path = _PROJECT_ROOT / "data" / "processed" / "chunks.json"



    print(f"\n{'=' * 60}")

    print("  Egyptian Law Assistant  Index Builder")

    print(f"{'=' * 60}")

    print(f"  Source : {chunks_path}")

    print(f"  Target : ./chroma_db/\n")



    #  Load chunks from Sprint 2 JSON output 

    if not chunks_path.exists():

        print(

            "[ERROR] data/processed/chunks.json not found.\n"

            "  Run Sprint 2 first: python -m src.document_processing.ingestion_pipeline"

        )

        sys.exit(1)



    raw = json.loads(chunks_path.read_text(encoding="utf-8"))

    chunks: list[DocumentChunk] = [DocumentChunk(**item) for item in raw]

    print(f"  Loaded {len(chunks)} chunks from JSON")



    #  Preview the translation 

    print("\n  Sample TextNode translation (first chunk):")

    sample_node = _chunk_to_text_node(chunks[0])

    print(f"    node.id_      = {sample_node.id_!r}")

    print(f"    node.text[:80]= {sample_node.text[:80]!r}...")

    print(f"    node.metadata = {sample_node.metadata}")



    #  Build index 

    print(f"\n  Starting embedding + indexing ({len(chunks)} articles)")

    print("  (Requires Ollama running with nomic-embed-text loaded)\n")



    try:

        active_settings = get_settings()

        print(f"  Collection : {get_collection_name(active_settings)}")

        print(f"  Embed model: {active_settings.embedding_model}")

        print(f"  Provider   : {active_settings.llm_provider}\n")



        index = build_index(chunks)



        print(f"\n{'' * 60}")

        print(f"  Index built successfully.")

        print(f"  Collection: {get_collection_name(active_settings)}")

        print(f"  Run the query API next: make up-api")

        print(f"{'=' * 60}\n")



    except EmbeddingError as exc:

        print(f"\n[ERROR] Embedding failed: {exc.message}")

        print("  Ensure Ollama is running: ollama serve")

        print(f"  Ensure model is pulled : ollama pull {exc.model}")

        sys.exit(1)



    except IngestionError as exc:

        print(f"\n[ERROR] {exc.message}")

        sys.exit(1)





if __name__ == "__main__":

    main()
