# Purpose: connect the stages of the RAG workflow.
# Work: create embeddings, store and retrieve chunks, and generate answers from retrieved context.

import subprocess
import sys
from .chunking import chunk_pages
from .config import CHUNK_TOKENS, OVERLAP_TOKENS, INDEX_MANIFEST, TOP_K, PROJECT_ROOT
from .documents import load_pdf_pages
from .embeddings import token_count
from .generation import LocalGenerator, REFUSAL
from .retrieval import load_manifest, retrieve, save_index

BUILD_SIGNATURE = f"math-cache-3:chunk-v1:parent-pages-v2:{CHUNK_TOKENS}:{OVERLAP_TOKENS}"


def ingest(rebuild=False, refresh_ocr=False):
    # Reuse a current index without repeating model processing.
    if INDEX_MANIFEST.exists() and not rebuild and not refresh_ocr:
        try:
            manifest = load_manifest()
            if manifest.get("build_signature") == BUILD_SIGNATURE:
                print(f"Index already current: {manifest['chunk_count']} chunks.")
                return manifest
        except (ValueError, FileNotFoundError):
            pass
    # Run OCR in a child process so its model memory is released before embedding.
    command = [sys.executable, str(PROJECT_ROOT / "preview.py"), "--prepare-only"]
    if refresh_ocr:
        command.append("--refresh")
    subprocess.run(command, check=True)
    pages = load_pdf_pages()
    if any(not page["text"].strip() for page in pages):
        raise ValueError("Some pages have no extracted text. Inspect with preview.py before indexing.")
    chunks = chunk_pages(pages, token_count, CHUNK_TOKENS, OVERLAP_TOKENS)
    return save_index(chunks, len(pages), BUILD_SIGNATURE, pages=pages)


def ask(question, generator=None, top_k=TOP_K, week=None, retrieve_only=False):
    search = retrieve(question, top_k=top_k, week=week)
    if not search["supported"]:
        return {"question": question, "answer": REFUSAL, "sources": [], "mode": "no_support",
                "best_similarity": search["best_similarity"]}
    if retrieve_only:
        return {"question": question, "answer": "Retrieved PDF passages (no generated answer):", "sources": search["hits"], "mode": "retrieval"}
    if generator is None:
        with LocalGenerator() as local:
            result = local.generate(question, search["hits"])
    else:
        result = generator.generate(question, search["hits"])
    return dict(result, question=question, best_similarity=search["best_similarity"])
