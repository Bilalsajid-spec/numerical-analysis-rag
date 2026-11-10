# Purpose: download and prepare the free local embedding and answer models.
# Work: download pinned artifacts from official sources, verify checksums, and extract the runtime.

import hashlib
import json
import sys
import time
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from rag_nm.config import DATA_DIR, EMBEDDING_DIR, EMBEDDING_MODEL, LLM_MODEL_PATH, RUNTIME_DIR

RUNTIME_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b11960/llama-b11960-bin-win-cpu-x64.zip"
RUNTIME_SHA = "73f962f82850d244db47eaacb9d913637027b82399124324298576d58c5f4287"
MODEL_REVISION = "91cad51170dc346986eccefdc2dd33a9da36ead9"
MODEL_SHA = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
MODEL_URL = f"https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/{MODEL_REVISION}/{LLM_MODEL_PATH.name}?download=true"


def digest(path):
    # Hash large model files in blocks without loading the whole file into RAM.
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download(url, path, expected):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and digest(path) == expected:
        print(f"Verified existing: {path.name}", flush=True)
        return
    partial = path.with_suffix(path.suffix + ".part")
    for attempt in range(5):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            with requests.get(url, headers=headers, stream=True, timeout=120) as response:
                response.raise_for_status()
                # Restart the file download if the server does not support resuming.
                resume = offset > 0 and response.status_code == 206
                if resume and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                    raise ValueError("Download resume range mismatch")
                received = offset if resume else 0
                checkpoint = received
                with partial.open("ab" if resume else "wb") as file:
                    for chunk in response.iter_content(1024 * 1024):
                        file.write(chunk)
                        received += len(chunk)
                        if received - checkpoint >= 50 * 1024 * 1024:
                            print(f"{path.name}: {received / 1024**2:.0f} MB downloaded", flush=True)
                            checkpoint = received
            if digest(partial) != expected:
                raise ValueError(f"Checksum mismatch: {path.name}")
            partial.replace(path)
            print(f"Downloaded and verified: {path.name}", flush=True)
            return
        except (requests.RequestException, OSError) as error:
            if attempt == 4:
                raise
            print(f"Retrying {path.name}: {error}", flush=True)
            time.sleep(2)


def setup_runtime():
    archive = DATA_DIR / "runtime" / "llama-b11960.zip"
    download(RUNTIME_URL, archive, RUNTIME_SHA)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        # Reject archive paths that escape the intended runtime directory.
        root = RUNTIME_DIR.resolve()
        for name in bundle.namelist():
            if not (root / name).resolve().is_relative_to(root):
                raise ValueError("Invalid runtime archive path")
        for info in bundle.infolist():
            target = root / info.filename
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            # Compare CRC values and skip unchanged runtime files that may already be in use.
            if target.is_file() and target.stat().st_size == info.file_size:
                checksum = 0
                with target.open("rb") as file:
                    for chunk in iter(lambda: file.read(1024 * 1024), b""):
                        checksum = zlib.crc32(chunk, checksum)
                if checksum == info.CRC:
                    continue
            bundle.extract(info, root)
    if not list(RUNTIME_DIR.rglob("llama-server.exe")):
        raise FileNotFoundError("llama-server.exe not found in runtime archive")
    print("Windows CPU runtime ready", flush=True)


def setup_embeddings():
    from huggingface_hub import snapshot_download
    # Download only PyTorch/safetensors and tokenizer files, excluding other backends.
    snapshot_download(EMBEDDING_MODEL, local_dir=str(EMBEDDING_DIR),
                      allow_patterns=["*.json", "*.txt", "*.safetensors", "1_Pooling/*"])
    print("Embedding model ready", flush=True)


def main():
    if sys.platform != "win32":
        raise RuntimeError("This runtime setup targets Windows x64.")
    # Run independent downloads concurrently without loading models for inference.
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(setup_runtime), pool.submit(setup_embeddings),
                pool.submit(download, MODEL_URL, LLM_MODEL_PATH, MODEL_SHA)]
        for job in jobs:
            job.result()
    (DATA_DIR / "model_manifest.json").write_text(json.dumps({
        "answer_model": "Qwen2.5-1.5B-Instruct Q4_K_M", "answer_revision": MODEL_REVISION,
        "answer_sha256": MODEL_SHA, "runtime": "llama.cpp b11960", "runtime_sha256": RUNTIME_SHA,
        "embedding_model": EMBEDDING_MODEL,
    }, indent=2), encoding="utf-8")
    print("All local models ready. Next: python ingest.py")


if __name__ == "__main__":
    main()
