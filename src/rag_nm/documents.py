# Purpose: prepare PDF content for searching.
# Work: select PDFs and pages and return OCR or plain extraction with source metadata.

# Use PyMuPDF to open PDFs and read their pages.
import pymupdf

# Read the notes directory from the shared configuration module.
from .config import NOTES_DIR

# Delegate formula extraction to the OCR module and handle selection here.
from .math_ocr import read_math_page


# Return a list of extracted page records from the selected PDFs.
def load_pdf_pages(use_math=True, pdf_name=None, page_number=None, refresh=False):
    # Require a PDF filename when selecting a page; page numbers start at one.
    if page_number is not None and (not pdf_name or page_number < 1):
        raise ValueError("A page number must be at least 1 and requires a PDF filename.")
    # Check that the notes directory exists.
    if not NOTES_DIR.is_dir():
        raise FileNotFoundError(f"PDF folder not found: {NOTES_DIR}")

    # Discover PDF files and process them in filename order.
    pdf_files = sorted(NOTES_DIR.glob("*.pdf"))

    # Report a clear error if the directory contains no PDFs.
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {NOTES_DIR}")

    # Restrict the selection when a specific PDF is requested.
    if pdf_name:
        pdf_files = [path for path in pdf_files if path.name == pdf_name]
        if not pdf_files:
            raise FileNotFoundError(f"PDF not found in notes: {pdf_name}")

    # Collect page text and source metadata in this list.
    pages = []

    # Open and process one PDF at a time.
    for pdf_path in pdf_files:
        # The context manager closes the PDF automatically.
        with pymupdf.open(pdf_path) as pdf:
            if page_number is not None and page_number > len(pdf):
                raise ValueError(f"{pdf_path.name} has only {len(pdf)} pages.")
            # Enumerate PDF pages using one-based page numbers.
            for current_page, page in enumerate(pdf, start=1):
                if page_number is not None and current_page != page_number:
                    continue

                # Use cached formula-aware extraction by default to avoid repeated OCR.
                if use_math:
                    pages.append(read_math_page(pdf_path, current_page, refresh=refresh))
                    continue

                # Plain extraction is a comparison mode selected with use_math=False.
                # Extract page text and request a sorted reading order.
                # Remove leading and trailing whitespace with strip().
                text = page.get_text("text", sort=True).strip()

                # Keep the PDF filename, page number, and extracted text together.
                # Preserve references so the original PDF page can be located later.
                pages.append({
                    "source": pdf_path.name,
                    "page": current_page,
                    "text": text,
                })

    # Retain empty records so the preview can identify extraction failures.
    # The pipeline delegates chunk creation to the separate chunking module.
    return pages
