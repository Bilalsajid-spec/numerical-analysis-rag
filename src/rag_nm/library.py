# Purpose: discover current PDF files and their optional week numbers.
# Work: share one filename-based document catalogue between the API and retrieval.

import re

from .config import NOTES_DIR


def list_documents():
    # Parse filenames such as Week_9_Numerical_Analysis.pdf into week filter options.
    # Include PDFs with other names in the All notes search.
    documents = []
    for path in sorted(NOTES_DIR.glob("*.pdf")):
        if not path.is_file():
            continue
        match = re.match(r"^Week_(\d+)_", path.name, re.IGNORECASE)
        week = int(match.group(1)) if match else None
        documents.append({"source": path.name, "week": week if week and week > 0 else None})
    return documents
