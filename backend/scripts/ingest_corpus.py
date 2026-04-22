#!/usr/bin/env python3
"""
backend/scripts/ingest_corpus.py
==================================
CLI script to ingest medical knowledge into Qdrant.

Supports:
- PDF ingestion (textbooks, encyclopedias)
- PMC Open Access XML ingestion (research articles)

Usage examples:

PDF:
    python ingest_corpus.py --pdf ../medical_book.pdf --doc-type textbook

PMC XML folder:
    python ingest_corpus.py --pmc-dir ../PMC010 --doc-type research

Options:
    --pdf           Path to a PDF file
    --pmc-dir       Path to a folder containing PMC XML files
    --collection    Qdrant collection name (default: global_knowledge)
    --doc-type      Document type tag (textbook | encyclopedia | research)
    --disease       Optional disease tag
    --organ-system  Optional organ system tag
    --clear         Clear collection before ingestion
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import os
from pathlib import Path
import xml.etree.ElementTree as ET

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ingestion import Ingestion
from core.vectorstore import get_vectorstore

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest_corpus")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest medical knowledge into Qdrant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", help="Path to a PDF file")
    src.add_argument("--pmc-dir", help="Path to folder with PMC XML files")

    parser.add_argument("--collection", default="global_knowledge")
    parser.add_argument("--doc-type", default="textbook")
    parser.add_argument("--disease", default="")
    parser.add_argument("--organ-system", default="")
    parser.add_argument("--clear", action="store_true")

    return parser.parse_args()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def progress_callback(current: int, total: int) -> None:
    pct = (current / total) * 100
    bar_len = 40
    filled = int(bar_len * current / total)
    bar = "█" * filled + "─" * (bar_len - filled)
    print(f"\r  [{bar}] {pct:5.1f}%  Page {current}/{total}", end="", flush=True)


def extract_text_from_pmc_xml(xml_path: Path) -> str:
    """
    Extracts clean biomedical text from a PMC XML file.
    Simple, fast, and academically acceptable.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        logger.warning("Failed to parse %s (%s)", xml_path.name, e)
        return ""

    texts: list[str] = []

    for elem in root.iter():
        if elem.text:
            txt = elem.text.strip()
            if len(txt) > 40:  # filter noise
                texts.append(txt)

    return "\n".join(texts)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    logger.info("=" * 60)
    logger.info("Medical Corpus Ingestion Pipeline")
    logger.info("=" * 60)
    logger.info("Collection: %s", args.collection)
    logger.info("Doc type:   %s", args.doc_type)
    logger.info("=" * 60)

    vs = get_vectorstore()

    # Optional clear
    if args.clear:
        logger.warning("--clear flag set. Clearing collection '%s'", args.collection)
        vs.recreate_collection(args.collection)

    before_count = vs.count(args.collection)
    logger.info("Vectors before ingestion: %d", before_count)

    ing = Ingestion()
    t_start = time.perf_counter()
    total_chunks = 0

    # -----------------------------------------------------------------------
    # PDF ingestion
    # -----------------------------------------------------------------------
    if args.pdf:
        pdf_path = Path(args.pdf).resolve()
        if not pdf_path.exists():
            logger.error("PDF not found: %s", pdf_path)
            sys.exit(1)

        logger.info("Ingesting PDF: %s", pdf_path.name)

        metadata = {
            "doc_type": args.doc_type,
            "disease": args.disease,
            "organ_system": args.organ_system,
            "source": pdf_path.name,
        }

        print()
        total_chunks = ing.ingest_pdf(
            pdf_path=str(pdf_path),
            collection=args.collection,
            metadata=metadata,
            progress_callback=progress_callback,
        )
        print()

    # -----------------------------------------------------------------------
    # PMC XML ingestion
    # -----------------------------------------------------------------------
    if args.pmc_dir:
        pmc_dir = Path(args.pmc_dir).resolve()
        if not pmc_dir.exists() or not pmc_dir.is_dir():
            logger.error("PMC directory not found: %s", pmc_dir)
            sys.exit(1)

        xml_files = sorted(pmc_dir.glob("*.xml"))
        logger.info("Ingesting PMC XML folder: %s (%d files)", pmc_dir.name, len(xml_files))

        for idx, xml_file in enumerate(xml_files, start=1):
            logger.info("[%d/%d] Processing %s", idx, len(xml_files), xml_file.name)

            text = extract_text_from_pmc_xml(xml_file)
            if not text.strip():
                continue

            metadata = {
                "doc_type": args.doc_type,
                "disease": args.disease,
                "organ_system": args.organ_system,
                "source": "PubMed Central",
                "file": xml_file.name,
            }

            chunks = ing.ingest_text(
                text=text,
                collection=args.collection,
                metadata=metadata,
            )
            total_chunks += chunks

    elapsed = time.perf_counter() - t_start
    after_count = vs.count(args.collection)

    logger.info("=" * 60)
    logger.info("✅ Ingestion Complete!")
    logger.info("  Chunks added:   %d", total_chunks)
    logger.info("  Time elapsed:   %.1f seconds", elapsed)
    logger.info("  Rate:           %.2f chunks/sec", total_chunks / max(elapsed, 0.001))
    logger.info("  Vectors before: %d  →  after: %d", before_count, after_count)
    logger.info("  Collection '%s' ready for retrieval.", args.collection)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()