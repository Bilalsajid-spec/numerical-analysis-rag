# Purpose: prepare embedding and answer weights without installing a runtime.
# Work: reuse the existing download functions from inside a Docker container.

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Make the project's root-level setup module importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Import functions without executing setup_models.py's main function.
from setup_models import download, setup_embeddings, MODEL_URL, MODEL_SHA
from rag_nm.config import LLM_MODEL_PATH


def main():
    # Download independent model artifacts concurrently.
    # The existing download function verifies the answer model checksum.
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(setup_embeddings),
            pool.submit(download, MODEL_URL, LLM_MODEL_PATH, MODEL_SHA),
        ]

        # Report failures instead of claiming that setup succeeded.
        for job in jobs:
            job.result()

    print("Embedding and answer models are ready.")
    print("Next: add PDFs to notes/ and run ingestion.")


if __name__ == "__main__":
    main()