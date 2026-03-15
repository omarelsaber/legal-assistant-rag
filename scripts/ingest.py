"""
Ingestion entry point — called by ``make ingest``.

Workflow
─────────
  1. Read all .txt files from data/raw/
  2. Parse Arabic مادة N headers → DocumentChunk objects
  3. Embed chunks with Ollama (nomic-embed-text)
  4. Upsert vectors into ChromaDB (config-namespaced collection)
  5. Print a summary: articles indexed, collection name, vector count

Prerequisites
──────────────
  - Ollama running       : ollama serve
  - Embedding model      : ollama pull nomic-embed-text
  - Clean Arabic data    : python scripts/convert_data.py
  - No stale ChromaDB    : rm -rf chroma_db   (if re-indexing from scratch)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

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

    settings        = get_settings()
    raw_dir         = _PROJECT_ROOT / "data" / "raw"
    collection_name = get_collection_name(settings)

    print(f"\n{'=' * 60}")
    print("  Egyptian Law Assistant — Ingestion Pipeline")
    print(f"{'=' * 60}")
    print(f"  Source dir      : {raw_dir}")
    print(f"  Collection      : {collection_name}")
    print(f"  Embed model     : {settings.embedding_model}")
    print(f"  LLM provider    : {settings.llm_provider}\n")

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
    print(f"\n  Embedding {len(all_chunks):,} articles …")
    print("  (First run may take several minutes)\n")

    try:
        build_index(all_chunks, settings=settings)
    except Exception as exc:
        print(f"\n[ERROR] Indexing failed: {exc}")
        print("  Is Ollama running?  ->  ollama serve")
        print(f"  Is model pulled?   ->  ollama pull {settings.embedding_model}")
        sys.exit(1)

    print(f"\n{'─' * 60}")
    print(f"  Ingestion complete!")
    print(f"  Collection      : {collection_name}")
    print(f"  Articles indexed: {len(all_chunks):,}")
    print(f"  Start the API   : python -m src.api.main")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()