# Purpose: extract PDF page text while preserving mathematical structure.
# Work: extract formulas as LaTeX using local OCR and cache each page result.

import hashlib
import json
import os
from functools import lru_cache
from importlib.metadata import version

from .config import EXTRACTED_DIR, OCR_MODELS_DIR


# Load the OCR engine once and reuse it for subsequent pages.
@lru_cache(maxsize=1)
def _get_engine():
    # Set the CPU device and local model directory before importing the OCR library.
    os.environ["MINERU_DEVICE_MODE"] = "cpu"
    os.environ["RAPID_MODELS_DIR"] = str(OCR_MODELS_DIR)

    # Import lazily so plain PDF previews do not load the OCR engine.
    from rapid_doc import RapidDoc

    # Enable recognition of inline and display equations.
    # Preserve table structure so numerical examples retain their row and column context.
    return RapidDoc(lang="en", formula_enable=True, table_enable=True, pdf_pages_batch=1)


def read_math_page(pdf_path, page_number, refresh=False):
    # Fingerprint PDF content and OCR settings to invalidate stale cached results.
    settings = f"rapid-doc={version('rapid-doc')};schema=3;lang=en;table=true"
    fingerprint = hashlib.sha256(pdf_path.read_bytes() + settings.encode()).hexdigest()[:20]
    page_dir = EXTRACTED_DIR / pdf_path.stem / fingerprint / f"page_{page_number:03d}"
    cache_path = page_dir / "record.json"

    # Return valid cached text without loading the OCR model or accessing the internet.
    if cache_path.exists() and not refresh:
        record = json.loads(cache_path.read_text(encoding="utf-8"))
        if (
            record.get("source") == pdf_path.name
            and record.get("page") == page_number
            and isinstance(record.get("text"), str)
            and record["text"].strip()
            and record.get("extraction_method") == "local_math_ocr"
        ):
            return record
        raise ValueError(f"Invalid OCR cache: {cache_path}; run with --refresh.")

    # Report progress because first-time model preparation and OCR can be slow.
    print(f"Local formula OCR: {pdf_path.name}, PDF page {page_number}", flush=True)
    page_dir.mkdir(parents=True, exist_ok=True)

    # Convert one-based project page numbers to zero-based library page indexes.
    # Use equal start and end indexes to process exactly one requested page.
    result = _get_engine()(
        pdf_path,
        start_page_id=page_number - 1,
        end_page_id=page_number - 1,
        output_dir=page_dir / "artifacts",
    )

    # Reject empty OCR output rather than silently substituting damaged plain text.
    if not result.markdown.strip():
        raise ValueError(f"OCR returned no text: {pdf_path.name}, page {page_number}")

    # Preserve LaTeX formulas inside inline and display dollar delimiters.
    # Mark OCR output for review; successful extraction does not prove mathematical accuracy.
    # Point Markdown image links to their correct relative artifact paths.
    text = result.markdown.strip()
    for image_path in (page_dir / "artifacts").rglob("*"):
        if image_path.is_file() and image_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            target = image_path.relative_to(page_dir).as_posix()
            text = text.replace(f"(images/{image_path.name})", f"({target})")

    # Use original PDF positions to restore simple table scripts.
    # Restore only matching, unambiguous cells and preserve complex OCR expressions.
    from .table_math import restore_table_scripts
    text, restored = restore_table_scripts(text, getattr(result, "middle_json", None), pdf_path, page_number)

    record = {
        "source": pdf_path.name,
        "page": page_number,
        "text": text,
        "extraction_method": "local_math_ocr",
        "review_required": True,
        "table_scripts_restored": restored,
    }

    # Save readable Markdown and a machine-readable JSON page record.
    (page_dir / "page.md").write_text(record["text"], encoding="utf-8")
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(cache_path)
    return record
