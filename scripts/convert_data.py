"""
Convert TawasulAI/egyptian-law-articles parquet → pipeline-ready UTF-8 text.

Confirmed schema (from probe_parquet.py):
    Each row in 'articles' is a dict with keys:
        number  : str   — article number, ASCII digits e.g. '1', '42'
        page    : int   — source page (not used)
        text_ar : str   — Arabic article text (may contain Arabic-Indic
                          sub-clause markers like (۱)(۲) — these are safe,
                          the ingestion regex only matches ASCII \\d+ after مادة)
        text_en : str   — English translation (not used)

Output format per article:
    المادة 42
    نص المادة كاملاً هنا...
    --------------------------------------------------

The --- separators are cosmetic. _SEPARATOR_RE in ingestion_pipeline.py
strips all dash-run lines during cleaning, so they never enter ChromaDB.

Run:
    python scripts/convert_data.py
    python scripts/convert_data.py --input data/0000.parquet --output data/raw/egyptian_laws.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_SEPARATOR = "-" * 50


def convert(input_path: Path, output_path: Path) -> None:
    try:
        import pandas as pd
    except ImportError:
        print("[ERROR] pandas is not installed. Run: pip install pandas pyarrow")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("  Egyptian Law Data Converter")
    print(f"{'=' * 60}")
    print(f"\n  Source : {input_path}")
    print(f"  Target : {output_path}\n")

    # ── 1. Load ────────────────────────────────────────────────────────────────
    if not input_path.exists():
        print(f"[ERROR] Not found: {input_path.resolve()}")
        print("  Download: huggingface-cli download TawasulAI/egyptian-law-articles "
              "--repo-type dataset --local-dir data")
        sys.exit(1)

    print(f"  Loading {input_path.name} …")
    df = pd.read_parquet(input_path)
    print(f"  Rows loaded : {len(df):,}")

    # ── 2. Unpack the 'articles' dict column ───────────────────────────────────
    # Each cell is already a dict: {"number": "1", "text_ar": "...", ...}
    #  Stage 2: Expand and Clean
    expanded_rows: list[dict[str, str]] = []
    skipped_count: int = 0
    written_count: int = 0

    print("  Unpacking 'articles' column …")
    articles_df = pd.json_normalize(df["articles"])
    print(f"  Columns after unpack : {list(articles_df.columns)}")

    # Validate the columns we need exist
    for required in ("number", "text_ar"):
        if required not in articles_df.columns:
            print(f"[ERROR] Expected column '{required}' not found after unpacking.")
            print(f"  Available columns: {list(articles_df.columns)}")
            sys.exit(1)

    # ── 3. Clean ───────────────────────────────────────────────────────────────
    total_articles = len(articles_df)
    
    # Iterate and clean, populating expanded_rows and counting skipped
    for _, row in articles_df.iterrows():
        number_raw  = row.get("number")
        text_ar_raw = row.get("text_ar")

        number  = str(number_raw).strip() if number_raw is not None else ""
        text_ar = str(text_ar_raw).strip() if text_ar_raw is not None else ""

        if not number or not text_ar or text_ar == "nan":
            skipped_count += 1
            continue

        expanded_rows.append(
            {
                "number": number,
                "text_ar": text_ar,
            }
        )
        written_count += 1

    # Recreate articles_df from cleaned rows for subsequent steps
    articles_df = pd.DataFrame(expanded_rows)

    print(f"\n  Total articles  : {total_articles:,}")
    if skipped_count:
        print(f"  Skipped (empty) : {skipped_count:,}")
    print(f"  To be written   : {written_count:,}")

    # ── 4. Sort by article number (numeric, not lexicographic) ────────────────
    articles_df["_n"] = pd.to_numeric(
        articles_df["number"].astype(str).str.strip(), errors="coerce"
    ).fillna(0).astype(int)
    articles_df = articles_df.sort_values("_n").reset_index(drop=True)

    # ── 5. Write UTF-8 text file ───────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Reset written_count for the actual file writing loop
    written_count = 0 

    with output_path.open("w", encoding="utf-8") as fh:
        for _, row in articles_df.iterrows():
            number  = str(row["number"]).strip()
            text_ar = str(row["text_ar"]).strip()

            # This check is redundant if the cleaning in step 3 was thorough,
            # but kept for robustness in case of unexpected data issues post-sort.
            if not number or not text_ar or text_ar == "nan":
                continue

            fh.write(f"المادة {number}\n")
            fh.write(f"{text_ar}\n")
            fh.write(_SEPARATOR + "\n\n")
            written_count += 1

    # ── 5.1 Write Metadata JSON Sidecar ───────────────────────────────────────
    metadata_output_path = output_path.with_name(f"{output_path.stem}_metadata.json")
    print(f"  Writing metadata sidecar to: {metadata_output_path.name}")
    import json
    metadata_dict = {}
    for _, row in articles_df.iterrows():
        number = str(row["number"]).strip()
        if not number:
            continue
        try:
            num_int = int(number.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
            metadata_dict[str(num_int)] = {
                "law_name": "Unknown Law",
                "law_year": None
            }
        except ValueError:
            continue
            
    with metadata_output_path.open("w", encoding="utf-8") as fh:
        json.dump(metadata_dict, fh, ensure_ascii=False, indent=2)

    # ── 6. Verify ──────────────────────────────────────────────────────────────
    size_mb = output_path.stat().st_size / (1024 * 1024)

    print(f"\n  {'─' * 50}")
    print(f"  Articles written : {written_count:,}")
    print(f"  File size        : {size_mb:.2f} MB")
    print(f"  Encoding         : UTF-8  ✓")

    print(f"\n  Spot-check (first 3 article headers):")
    with output_path.open("r", encoding="utf-8") as fh:
        found = 0
        for line in fh:
            if line.startswith("المادة"):
                print(f"    {line.rstrip()}")
                found += 1
                if found == 3:
                    break

    print(f"\n  {'=' * 50}")
    print(f"  Conversion complete!")
    print(f"\n  Next steps:")
    print(f"    1.  rm -rf chroma_db")
    print(f"    2.  make ingest")
    print(f"  {'=' * 50}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert TawasulAI/egyptian-law-articles parquet → UTF-8 text"
    )
    parser.add_argument("--input",  type=Path, default=Path("data/0000.parquet"))
    parser.add_argument("--output", type=Path, default=Path("data/raw/egyptian_laws.txt"))
    args = parser.parse_args()
    convert(args.input, args.output)


if __name__ == "__main__":
    main()