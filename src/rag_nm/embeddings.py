# Purpose: encode PDF chunks and questions as comparable numerical vectors.
# Work: load and reuse the downloaded MiniLM encoder on the CPU.

import hashlib
from functools import lru_cache
from .config import EMBEDDING_DIR


@lru_cache(maxsize=1)
def get_encoder():
    if not (EMBEDDING_DIR / "model.safetensors").exists():
        raise FileNotFoundError("Embedding model missing. Run python setup_models.py first.")
    from sentence_transformers import SentenceTransformer
    # Load only local model files during question answering.
    return SentenceTransformer(str(EMBEDDING_DIR), device="cpu", local_files_only=True)


def token_count(text):
    # Count tokens without treating a long equation as an inference request.
    return len(get_encoder().tokenizer.encode(text, add_special_tokens=False, verbose=False))


def encode(texts):
    return get_encoder().encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False).tolist()


def embedding_fingerprint():
    # Detect changed model weights so a stale vector index is not reused.
    path = EMBEDDING_DIR / "model.safetensors"
    if not path.exists():
        raise FileNotFoundError("Run python setup_models.py first.")
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for data in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(data)
    return hasher.hexdigest()
