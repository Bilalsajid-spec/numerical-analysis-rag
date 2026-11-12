# Purpose: install the verified Linux CPU runtime inside the Docker image.
# Work: download llama.cpp, verify its checksum, and extract its executable.

import hashlib
import platform
import sys
import tarfile
import urllib.request
from pathlib import Path

# This artifact supports Linux x64 containers.
if sys.platform != "linux" or platform.machine().lower() != "x86_64":
    raise RuntimeError("This installer requires Linux x64.")

# Use the same llama.cpp release as the existing Windows runtime.
URL = (
    "https://github.com/ggml-org/llama.cpp/releases/download/"
    "b11960/llama-b11960-bin-ubuntu-x64.tar.gz"
)
EXPECTED_SHA256 = (
    "31cc3a6bc638ac6c48dc4b1b74888f1eaadf3d14227c1e5f67daf9a49541d97a"
)

archive = Path("/tmp/llama-runtime.tar.gz")
destination = Path("/opt/llama")

# Download the official CPU runtime archive.
urllib.request.urlretrieve(URL, archive)

# Reject a download whose contents do not match the expected checksum.
actual_checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
if actual_checksum != EXPECTED_SHA256:
    raise RuntimeError("Runtime download checksum mismatch.")

# Extract safely, rejecting paths that escape the destination.
destination.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive, "r:gz") as bundle:
    bundle.extractall(destination, filter="data")

# Confirm that the server exists and grant executable permission.
binary = next(destination.rglob("llama-server"), None)
if binary is None:
    raise FileNotFoundError("llama-server is missing from the archive.")

binary.chmod(binary.stat().st_mode | 0o111)

# Remove the downloaded archive after successful installation.
archive.unlink()
print(f"Linux runtime installed: {binary}")