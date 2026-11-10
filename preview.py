# Purpose: inspect PDF text before building the index.
# Work: display page counts and sample text so we can check extraction quality.

# Use sys to configure Python import paths and terminal output.
import sys

# Use argparse to select a PDF, page, and preview mode from the command line.
import argparse

# Resolve the src folder relative to this script using Path.
from pathlib import Path

# Add src to the import path so Python can find the rag_nm package.
# Use __file__ so imports also work when launched from another working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Reuse the extraction function from documents.py.
from rag_nm.documents import load_pdf_pages


# Display the extracted text in the terminal.
def preview_pdfs(pdf_name=None, page_number=None, use_math=True, show_full=False, refresh=False, prepare_only=False):
    # Read page text and source metadata from the selected PDFs.
    pages = load_pdf_pages(
        use_math=use_math, pdf_name=pdf_name, page_number=page_number, refresh=refresh,
    )

    # Deduplicate filenames with a set and sort them for consistent output.
    pdf_names = sorted({page["source"] for page in pages})

    # Display the total PDF and page counts first.
    print(f"Total PDFs: {len(pdf_names)}")
    print(f"Total pages: {len(pages)}")
    print(f"Extraction mode: {'local formula OCR (LaTeX)' if use_math else 'plain text (formulas may be broken)'}")
    if prepare_only:
        print("Page extraction cache ready.")
        return

    # Display a summary and first-page sample for each PDF.
    for pdf_name in pdf_names:
        # Select only the records belonging to this PDF.
        pdf_pages = [page for page in pages if page["source"] == pdf_name]

        # Index zero selects the first page record in this list.
        sample_page = pdf_pages[0]

        # Show the filename, selected-page count, and original PDF page number.
        print("\n" + "=" * 60)
        print(f"PDF: {pdf_name}")
        print(f"Pages selected: {len(pdf_pages)}")
        print(f"Sample from PDF page: {sample_page['page']}")
        print("Full selected page text:" if show_full else "First 700 characters:")

        # Limit the preview to 700 characters to keep terminal output manageable.
        if sample_page["text"]:
            print(sample_page["text"] if show_full else sample_page["text"][:700])

            # Show every selected page when --full is enabled.
            if show_full:
                for extra_page in pdf_pages[1:]:
                    print(f"\nPDF page: {extra_page['page']}")
                    print(extra_page["text"])
        else:
            print("No text extracted from this page; check the original PDF.")

    # Check all selected pages for empty text, not just the displayed sample.
    empty_pages = [page for page in pages if not page["text"]]
    print(f"\nPages with no extracted text: {len(empty_pages)}")

    # Identify the filename and page number of each empty extraction.
    for page in empty_pages:
        print(f"Check: {page['source']}, PDF page {page['page']}")


# Run this block when preview.py is executed directly.
# Importing this module does not automatically run the preview.
if __name__ == "__main__":
    # Use UTF-8 output for Greek letters and mathematical symbols.
    sys.stdout.reconfigure(encoding="utf-8")

    # Use formula-aware extraction by default; --plain shows the comparison mode.
    parser = argparse.ArgumentParser(description="Preview numerical analysis PDF text and formulas")
    parser.add_argument("--pdf", help="PDF filename inside notes/, for example Week_8_Numerical_Analysis.pdf")
    parser.add_argument("--page", type=int, help="PDF page number, starting at 1; requires --pdf")
    parser.add_argument("--plain", action="store_true", help="Compare original plain text extraction")
    parser.add_argument("--full", action="store_true", help="Show full text of all selected pages")
    parser.add_argument("--refresh", action="store_true", help="Run OCR again instead of using cached text")
    parser.add_argument("--prepare-only", action="store_true", help="Prepare cache without printing sample text")
    args = parser.parse_args()
    try:
        preview_pdfs(args.pdf, args.page, not args.plain, args.full, args.refresh, args.prepare_only)
    except (FileNotFoundError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")
