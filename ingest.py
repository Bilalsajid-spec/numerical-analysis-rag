# Purpose: entry point for building a searchable index from the syllabus PDFs.
# Work: call PDF extraction, chunking, embedding, and database storage step by step.

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from rag_nm.pipeline import ingest


def main():
    parser = argparse.ArgumentParser(description="Index all numerical analysis PDFs locally")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild vectors from cached OCR")
    parser.add_argument("--refresh-ocr", action="store_true", help="Recompute all PDF OCR before indexing")
    args = parser.parse_args()
    manifest = ingest(args.rebuild, args.refresh_ocr)
    print(f"READY: {manifest['pdf_count']} PDFs, {manifest['page_count']} pages, {manifest['chunk_count']} chunks")
    print(f"Oversize atomic chunks preserved: {manifest['oversize_atomic_chunks']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
