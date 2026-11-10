# Purpose: keep shared project settings in one place.
# Work: define PDF and database paths, load environment variables, and configure models.

# Use the standard-library Path class to construct filesystem paths.
from pathlib import Path
import os
from dotenv import load_dotenv

# Resolve this configuration file to an absolute path.
# parents[0] is rag_nm, parents[1] is src, and parents[2] is the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# Locate the notes directory containing the input PDFs.
# The / operator joins path components here.
NOTES_DIR = PROJECT_ROOT / "notes"

# Store generated project files in the data directory.
DATA_DIR = PROJECT_ROOT / "data"

# Store the persistent search database in data/chroma.
CHROMA_DIR = DATA_DIR / "chroma"

# Cache extracted page text for reuse on subsequent runs.
EXTRACTED_DIR = DATA_DIR / "extracted"

# Keep downloaded OCR model files inside the project.
OCR_MODELS_DIR = DATA_DIR / "models" / "ocr"

# Keep embedding and answer model artifacts in separate local directories.
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIR = DATA_DIR / "models" / "embeddings"
LLM_MODEL_DIR = DATA_DIR / "models" / "answer"
LLM_MODEL_PATH = LLM_MODEL_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
RUNTIME_DIR = DATA_DIR / "runtime" / "llama-b11960"
LLM_PORT = int(os.getenv("LLM_PORT", "8765"))
LLM_THREADS = int(os.getenv("LLM_THREADS", str(min(6, os.cpu_count() or 2))))
CHUNK_TOKENS = 180
OVERLAP_TOKENS = 25
TOP_K = 4
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.32"))
INDEX_MANIFEST = DATA_DIR / "index_manifest.json"

# Use the project cache as the default Hugging Face cache.
os.environ.setdefault("HF_HOME", str(DATA_DIR / "models" / "hf_cache"))

# Importing settings does not load OCR or answer models into RAM.
