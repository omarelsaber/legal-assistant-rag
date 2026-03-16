"""
Ingestion entry point — called by ``make ingest``.

Workflow
─────────
  1. Force EMBEDDING_INPUT_TYPE=search_document for this process only.
     (Cohere requires "search_document" during ingestion and "search_query"
      during querying. This is the critical difference.)
  2. Read all .txt files from data/raw/
  3. Parse Arabic مادة N headers → DocumentChunk objects
  4. Embed each chunk via Cohere embed-multilingual-v3.0
  5. Upsert vectors into ChromaDB (config-hash namespaced collection)
  6. Print summary: articles indexed, collection name, vector count

Prerequisites
──────────────
  - COHERE_API_KEY in .env   (free at dashboard.cohere.com)
  - GROQ_API_KEY   in .env   (for generation at query time)
  - Clean Arabic text        : python scripts/convert_data.py
  - No stale ChromaDB        : rm -rf chroma_db  (if re-indexing from scratch)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# ── CRITICAL: set input_type BEFORE importing config/settings ─────────────────
# Cohere embed-multilingual-v3.0 is an asymmetric model.
# Documents must be embedded with "search_document" to produce vectors that
# are compatible with "search_query" vectors at retrieval time.
# If both phases use "search_query", cosine similarity scores drop ~15-20%.
os.environ.setdefault("EMBEDDING_INPUT_TYPE", "search_document")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")


def main() -> None:
    from src.core.config import get_settings
    from src.core.exceptions import IngestionError
    from src.document_processing.ingestion_pipeline import process_egyptian_law
    from src.knowledge_base.indexer import build_index
    from src.knowledge_base.vector_store import get_collection_name

    # Clear settings cache so the EMBEDDING_INPUT_TYPE override is picked up
    get_settings.cache_clear()
    settings = get_settings()

    raw_dir         = _PROJECT_ROOT / "data" / "raw"
    collection_name = get_collection_name(settings)

    print(f"\n{'=' * 60}")
    print("  Egyptian Law Assistant — Ingestion Pipeline")
    print(f"{'=' * 60}")
    print(f"  Source dir        : {raw_dir}")
    print(f"  Collection        : {collection_name}")
    print(f"  Embedding model   : {settings.embedding_model}")
    print(f"  Embedding provider: {settings.embedding_provider}")
    print(f"  Input type        : {settings.embedding_input_type}  ← search_document for ingestion")
    print(f"  LLM provider      : {settings.llm_provider}\n")

    if settings.embedding_input_type != "search_document":
        print("[WARNING] EMBEDDING_INPUT_TYPE is not 'search_document'.")
        print("  This will degrade retrieval quality. The env override may have failed.")

    # ── Discover source files ──────────────────────────────────────────────────
    txt_files = sorted(raw_dir.glob("*.txt"))
    if not txt_files:
        print(f"[ERROR] No .txt files found in {raw_dir}.")
        print("  Run first: python scripts/convert_data.py")
        sys.exit(1)

    print(f"  Found {len(txt_files)} file(s):")
    for f in txt_files:
        print(f"    - {f.name}  ({f.stat().st_size / 1024:.1f} KB)")
    print()

    # ── Parse all files into DocumentChunks ───────────────────────────────────
    all_chunks = []
    failed     = []

    for txt_file in txt_files:
        try:
            chunks = process_egyptian_law(str(txt_file))
            all_chunks.extend(chunks)
            logger.info("  + %s  ->  %d articles", txt_file.name, len(chunks))
        except IngestionError as exc:
            logger.error("  x %s  --  %s", txt_file.name, exc.reason)
            failed.append(txt_file.name)

    if not all_chunks:
        print("\n[ERROR] No chunks produced.")
        print("  Verify that your .txt files contain Arabic مادة N article headers.")
        sys.exit(1)

    print(f"\n  Total articles parsed : {len(all_chunks):,}")
    if failed:
        print(f"  Failed files          : {failed}")

    # ── Embed and index ────────────────────────────────────────────────────────
    print(f"\n  Embedding {len(all_chunks):,} articles via Cohere …")
    print("  (Each batch is an HTTPS call — no local GPU needed)\n")

    try:
        build_index(all_chunks, settings=settings)
    except Exception as exc:
        print(f"\n[ERROR] Indexing failed: {exc}")
        print("  Check your COHERE_API_KEY in .env")
        print("  Check your internet connection")
        sys.exit(1)

    print(f"\n{'─' * 60}")
    print(f"  Ingestion complete!")
    print(f"  Collection        : {collection_name}")
    print(f"  Articles indexed  : {len(all_chunks):,}")
    print(f"  Start the API     : python -m src.api.main")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()