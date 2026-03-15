"""
Ingestion pipeline for Egyptian corporate law text files.

Responsibility (this module only):
  Read a raw UTF-8 legal text  clean it  split on article boundaries
   map each article into a DocumentChunk domain object.

This module is intentionally free of LlamaIndex, ChromaDB, or any I/O
beyond reading the source file and writing the inspection JSON in main().
Those concerns belong in knowledge_base/indexer.py.

Imports from this project:
  src.core.schemas     DocumentChunk (the domain contract)
  src.core.exceptions  IngestionError (non-fatal, caller decides to continue or abort)
"""

from __future__ import annotations

import gc
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, cast

# ---------------------------------------------------------------------------
# Adjust the path so this file can be run directly as a script
# (python -m src.document_processing.ingestion_pipeline) without installing
# the package. In normal application use, the regular package import works.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from src.core.exceptions import IngestionError
    from src.core.schemas import DocumentChunk, IngestionResult
except ImportError:
    # Fallback to relative imports if testing script locally
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.core.exceptions import IngestionError
    from src.core.schemas import DocumentChunk, IngestionResult  # noqa: E402

logger = logging.getLogger(__name__)


#  Constants 

# The compiled regex is a module-level constant so it is built exactly once,
# not on every function call.
#
# Pattern breakdown  reading left to right:
#
#   (?:...)          Non-capturing group  the whole article header is one unit.
#
#   \(?              Optional opening parenthesis  handles "(???? 3)".
#
#   (?:??)?          Optional definite article "??"  matches both
#                    "????" (indefinite) and "??????" (definite).
#
#   ?[\u0640]??      The letters ? and ? with an optional Arabic Tatweel
#                    character (U+0640, ?) between them.
#                    Tatweel is a purely typographic stretching glyph inserted
#                    by some Arabic word processors for justification:
#                       ????   normal
#                       ?????  with tatweel between ? and ?
#                       ???????  definite with tatweel
#
#   ?[\u0640]??      Similarly handles tatweel between ? and ?.
#
#   \)?              Optional closing parenthesis.
#
#   \s*              Zero or more whitespace characters between "????" and the number.
#
#   (\d+)            Capture group 1: the article number (one or more ASCII digits).
#                    Egyptian legal texts use ASCII digits (0-9), not Arabic-Indic
#                    (-), so \d is sufficient here. Add [\d-]+ if your corpus
#                    uses Arabic-Indic numerals.
#
#   [^\S\n]*         Any horizontal whitespace (spaces, tabs) but NOT a newline.
#                    This consumes the space/tab between the number and the first
#                    word of the article body on the same line, without eating the
#                    newline that may follow.
#
# Flags:
#   re.MULTILINE   ^ and $ match at line boundaries (not just string start/end).
#                   The pattern anchors to ^ so it only matches at the start of a
#                   line, preventing false positives inside article body text that
#                   might reference another article number mid-sentence.
#   re.UNICODE     Ensures \s, \d, and . respect Unicode categories (default in
#                   Python 3 but made explicit for readability).
#
_ARTICLE_HEADER_RE = re.compile(
    r"""
    (?:                 # non-capturing: the full article header token
        \(?             # optional opening parenthesis
        (?:\u0627\u0644)? # optional Arabic definite article "ال"
        \u0645\u0627\u062f\u0629[\u0640]? # مادة + optional tatweel
        \)?             # optional closing parenthesis
    )
    \s*                 # optional whitespace between keyword and number
    ([\d\u0660-\u0669]+)# CAPTURE GROUP 1: ASCII and Arabic-Indic digits
    [^\S\n]*            # consume trailing horizontal whitespace on the same line
    """,
    re.MULTILINE | re.UNICODE | re.VERBOSE,
)

# Translator for normalising Arabic-Indic digits to ASCII digits
ARABIC_TO_ASCII_TRANSLATOR = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

# Separator patterns used during cleaning.
# Covers em-dash runs, en-dash runs, underscore runs, and asterisk runs
# that legal typists use as decorative section dividers.
_SEPARATOR_RE = re.compile(r"[-\u2013\u2014_*]{3,}", re.UNICODE)

# Collapse three or more consecutive newlines into exactly two
# (preserving one blank line between paragraphs).
_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}", re.UNICODE)


#  Text Cleaning 

def clean_legal_text(raw_text: str) -> str:
    """
    Normalise raw Egyptian legal text before article splitting.

    Operations (in order):
      1. Strip leading / trailing whitespace from the whole document.
      2. Remove decorative separator lines (dash runs, underscore runs, etc.).
      3. Collapse runs of 3+ newlines into exactly two newlines.
      4. Strip leading / trailing whitespace from every individual line.

    Args:
        raw_text: The raw UTF-8 string read from the source file.

    Returns:
        A cleaned string ready for regex-based article splitting.
    """
    text = raw_text.strip()

    # Remove decorative separators (whole line or inline)
    text = _SEPARATOR_RE.sub("", text)

    # Normalise excessive blank lines
    text = _EXCESS_NEWLINES_RE.sub("\n\n", text)

    # Strip each line individually (removes mid-document indent artifacts)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)

    return text.strip()


#  Article Splitting 

def split_into_articles(clean_text: str) -> list[tuple[int, str, str]]:
    """
    Split a cleaned legal document into (article_number, article_text, context) tuples.

    Strategy:
      Use re.split() with a capturing group so the article numbers are
      returned interleaved with the article bodies in the result list.
      Then walk adjacent pairs to reconstruct (number, body) tuples.

    Args:
        clean_text: Output of clean_legal_text().

    Returns:
        A list of (article_number_int, article_body_str, context_str) tuples.
        The article body includes everything from just after the header
        up to (but not including) the next article header.

    Notes:
        - The preamble (text before the first المادة) is discarded. For this
          corpus the preamble is boilerplate decree language, not law content.
          If you need to preserve it, extend this function to return it
          separately as a special chunk.
        - Article bodies are stripped of leading/trailing whitespace.
    """
    # We use a comprehension and str() to satisfy Pyre's strict typing,
    # because re.split can return list[str | Any].
    parts = [str(x) for x in _ARTICLE_HEADER_RE.split(clean_text)]

    # parts[0] is the preamble (before the first المادة)  intentionally discarded.
    # Remaining elements alternate: article_number, article_body.
    # Parts[0] is the preamble. Extract any trailing sections (الباب, الفصل)
    # as the starting context for the first article.
    current_context = ""
    if parts[0].strip():
        # Split on newline followed by الباب, الفصل, or الفرع
        splits = [str(x) for x in re.split(r'\n(?=(?:الباب|الفصل|الفرع)\s)', parts[0].strip())]
        if len(splits) > 1:
            splits.pop(0)
            current_context = "\n".join(splits).strip()

    article_tuples: list[tuple[int, str, str]] = []

    # Start from index 1; step by 2 to pick up (number, body) pairs.
    for i in range(1, len(parts) - 1, 2):
        raw_article_number = parts[i].strip()
        try:
            art_num_str = raw_article_number.translate(ARABIC_TO_ASCII_TRANSLATOR)
            article_number = int(art_num_str)
        except ValueError:
            logger.warning("Could not parse article number to int: %s", raw_article_number)
            continue

        raw_body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        
        # Check for context headers at the END of this body that belong to the NEXT article
        splits = [str(x) for x in re.split(r'\n(?=(?:الباب|الفصل|الفرع)\s)', raw_body)]
        article_body = splits.pop(0).strip()
        next_context = "\n".join(splits).strip() if splits else ""

        if not article_body:
            logger.warning(
                "Article %s has an empty body after splitting  skipped.",
                article_number,
            )
            continue

        article_tuples.append((article_number, article_body, current_context))
        
        if next_context:
            current_context = next_context

    return article_tuples


#  Chunk ID Generation 

def _make_chunk_id(source_file: str, article_number: int, chunk_index: int) -> str:
    """
    Generate a deterministic chunk ID from source file, article number and
    the chunk index.

    We intentionally include ``chunk_index`` because some articles may be
    split more than once (either due to erroneous regex matches or future
    downstream chunking logic). Without the index two chunks coming from the
    same article would produce identical IDs and collision errors when
    inserting into ChromaDB. The index guarantees uniqueness while still
    being stable across re-ingestion of the same document.

    Using a hash instead of uuid4 keeps the identifier constant across runs
    which allows ChromaDB upserts to update existing vectors rather than
    creating duplicates.

    Args:
        source_file:    Filename of the source document.
        article_number: The extracted article number string.
        chunk_index:    Sequential index of the chunk within the document.

    Returns:
        A 16-character hex string unique to this (file, article, index)
        combination.
    """
    raw = f"{source_file}::article::{article_number}::chunk::{chunk_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


#  Main Public Interface 

def process_egyptian_law(file_path: str) -> list[DocumentChunk]:
    """
    Read, clean, split, and map a UTF-8 Egyptian law text file into DocumentChunks.

    This is the primary entry point for the document_processing bounded context.
    It performs no I/O other than reading the source file.

    Pipeline stages:
      1. Read   open file_path as UTF-8 text.
      2. Clean  remove separators, normalise whitespace.
      3. Split  apply _ARTICLE_HEADER_RE to extract (number, body) pairs.
      4. Map    construct a DocumentChunk for each pair.

    Args:
        file_path: Absolute or relative path to the source .txt file.

    Returns:
        A list of DocumentChunk objects, one per extracted article.
        Never returns an empty list without raising: if splitting yields
        zero articles, an IngestionError is raised so the caller can
        log and continue with the next file.

    Raises:
        IngestionError: If the file cannot be read, is empty after cleaning,
                        or yields zero articles after splitting.
    """
    path = Path(file_path)
    source_filename = path.name


    #  Stage 1: Read (force encoding utf-8)
    logger.info("Reading source file: %s", path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except FileNotFoundError:
        raise IngestionError(
            file_path=file_path,
            reason=f"File not found: {path.resolve()}",
        )
    except UnicodeDecodeError as exc:
        raise IngestionError(
            file_path=file_path,
            reason=(
                f"UTF-8 decoding failed at byte offset {exc.start}. "
                "Ensure the file is saved with UTF-8 encoding "
                "(not Windows-1256 أو ISO-8859-6)."
            ),
        )

    if not raw_text.strip():
        raise IngestionError(
            file_path=file_path,
            reason="File is empty or contains only whitespace.",
        )
        
    # Attempt to load JSON sidecar metadata
    metadata_sidecar: dict[str, dict[str, Any]] = {}
    sidecar_path = path.with_name(f"{path.stem}_metadata.json")
    if sidecar_path.exists():
        try:
            with open(sidecar_path, "r", encoding="utf-8") as f:
                metadata_sidecar = json.load(f)
            logger.info("Loaded metadata sidecar: %s", sidecar_path.name)
        except Exception as e:
            logger.warning("Failed to load sidecar %s: %s", sidecar_path.name, e)

    #  Stage 2: Clean 
    logger.info("Cleaning text from: %s", source_filename)
    clean_text = clean_legal_text(raw_text)

    #  Stage 3: Split 
    logger.info("Splitting articles in: %s", source_filename)
    article_pairs = split_into_articles(clean_text)

    if not article_pairs:
        raise IngestionError(
            file_path=file_path,
            reason=(
                "Regex splitting produced zero articles. "
                "Verify the file contains Arabic المادة markers "
                "and the encoding is correct."
            ),
        )

    logger.info("Found %d articles in: %s", len(article_pairs), source_filename)

    #  Stage 4: Map to DocumentChunk 
    chunks: list[DocumentChunk] = []

    for chunk_index, (article_number, article_body, context) in enumerate(article_pairs):
        raw_sidecar_meta = metadata_sidecar.get(str(article_number))
        sidecar_meta: dict[str, Any] = raw_sidecar_meta if raw_sidecar_meta is not None else {}
        law_name = str(sidecar_meta.get("law_name", source_filename.replace(".txt", "").replace("_", " ").title()))
        law_year_val = sidecar_meta.get("law_year")
        law_year = int(law_year_val) if law_year_val is not None else None
        
        chunk_meta = {
            "source_path": str(path.resolve()),
            "character_count": len(article_body),
            "law_name": law_name,
        }
        if law_year is not None:
            chunk_meta["law_year"] = law_year
        if context:
            chunk_meta["section"] = context[:300]

        chunk = DocumentChunk(
            chunk_id=_make_chunk_id(source_filename, article_number, chunk_index),
            source_file=source_filename,
            article_number=article_number,  # Now strictly integer
            content=article_body,
            metadata=chunk_meta,
        )
        chunks.append(chunk)

    return chunks


#  Batch Ingestion (used by scripts/ingest.py) 

def ingest_directory(
    directory: str,
    batch_size: int = 10,
) -> IngestionResult:
    """
    Process all .txt files in a directory using streaming batches.

    Memory strategy (Performance Decision #3):
      Files are processed in batches of `batch_size`. After each batch,
      the chunk list is explicitly deleted and gc.collect() is called to
      release memory before loading the next batch. This keeps peak memory
      proportional to batch_size, not total corpus size.

    Args:
        directory:  Path to the directory containing raw .txt files.
        batch_size: Number of files to hold in memory simultaneously.

    Returns:
        IngestionResult summarising files processed, chunks created, and failures.

    Raises:
        IngestionError: If `directory` does not exist.
    """
    import itertools
    # Using python's built in itertools instead of more_itertools for dependency reduction
    # for _idx, chunk_batch in enumerate(itertools.batched(chunks, max_batch_size)): runs

    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise IngestionError(
            file_path=directory,
            reason=f"Directory does not exist: {dir_path.resolve()}",
        )

    txt_files = sorted(dir_path.glob("*.txt"))
    if not txt_files:
        logger.warning("No .txt files found in: %s", directory)

    all_chunks: list[DocumentChunk] = []
    failed_files: list[str] = []

    for batch in itertools.batched(txt_files, batch_size):
        batch_chunks: list[DocumentChunk] = []

        for file_path in batch:
            try:
                file_chunks = process_egyptian_law(str(file_path))
                batch_chunks.extend(file_chunks)
                logger.info("  + %s  %d chunks", file_path.name, len(file_chunks))
            except IngestionError as exc:
                # Non-fatal: log the failure and continue with the next file.
                logger.error("  x %s  %s", file_path.name, exc.reason)
                failed_files.append(file_path.name)

        all_chunks.extend(batch_chunks)

        # Explicit memory release between batches (Performance Decision #3)
        del batch_chunks
        gc.collect()

    return IngestionResult(
        total_files_processed=len(txt_files) - len(failed_files),
        total_chunks_created=len(all_chunks),
        total_files_skipped=0,  # cache-based skipping implemented in knowledge_base/indexer.py
        failed_files=failed_files,
        collection_name="(set by knowledge_base.vector_store)",
    )


#  CLI / Inspection Entry Point 

def main() -> None:
    """
    Development / inspection entry point.

    Reads  : data/raw/corporate_law.txt
    Prints : article count, first/last article numbers, first 3 chunk previews
    Writes : data/processed/chunks.json  (full list, pretty-printed, UTF-8)

    Run with:
        python -m src.document_processing.ingestion_pipeline
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    input_path  = _PROJECT_ROOT / "data" / "raw"       / "corporate_law.txt"
    output_path = _PROJECT_ROOT / "data" / "processed" / "chunks.json"

    print(f"\n{'=' * 60}")
    print("  Egyptian Law Ingestion Pipeline  Inspection Run")
    print(f"{'=' * 60}")
    print(f"  Input : {input_path}")
    print(f"  Output: {output_path}\n")

    #  Run pipeline 
    try:
        chunks = process_egyptian_law(str(input_path))
    except IngestionError as exc:
        print(f"\n[ERROR] Ingestion failed: {exc.message}")
        print("  Ensure data/raw/corporate_law.txt exists and is UTF-8 encoded.")
        sys.exit(1)

    #  Print summary 
    print(f"  Articles extracted : {len(chunks)}")
    print(f"  First article      : {chunks[0].article_number}")
    print(f"  Last article       : {chunks[-1].article_number}")

    #  Preview first 3 chunks 
    print(f"\n{'-' * 60}")
    print("  PREVIEW  First 3 Chunks")
    print(f"{'-' * 60}")
    for chunk in chunks[:3]:
        print(f"\n  [{chunk.article_number}]  id={chunk.chunk_id}")
        preview = chunk.content[:200].replace("\n", " ")
        if len(chunk.content) > 200:
            preview += ""
        print(f"  {preview}")
        print(f"  metadata: {chunk.metadata}")

    #  Save to JSON 
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            [chunk.model_dump() for chunk in chunks],
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n{'-' * 60}")
    print(f"  Saved {len(chunks)} chunks to: {output_path}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
