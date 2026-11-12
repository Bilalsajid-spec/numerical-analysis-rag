# Purpose: define the environment used to run this project in Docker.
# Work: start with a Python base image, then add dependencies and application files.

FROM python:3.14-slim-trixie AS base

# Prevent Python from creating .pyc cache files.
ENV PYTHONDONTWRITEBYTECODE=1

# Print logs immediately so they appear in Docker output.
ENV PYTHONUNBUFFERED=1

# Use /app as the working directory inside the container.
WORKDIR /app





# Create the frontend build stage using our Python base.
FROM base AS frontend

# Copy the frontend dependency list into /app.
COPY requirements-frontend.txt ./

# Install frontend packages inside the image without keeping pip's download cache.
RUN python -m pip install --no-cache-dir -r requirements-frontend.txt


# Copy the frontend application into the image.
COPY frontend/ ./frontend/

# Copy the Streamlit configuration.
COPY .streamlit/ ./.streamlit/

# Document the port used by the frontend.
EXPOSE 5173

# Start Streamlit when the container starts.
CMD ["python", "-m", "streamlit", "run", "frontend/app.py", "--server.address", "0.0.0.0", "--server.port", "5173"]



# Create a separate backend stage using the shared Python environment.
FROM base AS backend

# Install Linux system libraries needed by OCR and local CPU inference.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
    libstdc++6 \
    libgl1 \
    libglib2.0-0t64 \
    libcurl4t64 \
    && rm -rf /var/lib/apt/lists/*


    # Install CPU-only PyTorch for local embedding inference.
RUN python -m pip install --no-cache-dir torch==2.15.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Copy the backend dependency list into the image.
COPY requirements.txt ./

# Install the project's Python dependencies.
RUN python -m pip install --no-cache-dir -r requirements.txt


# Copy Python package metadata.
COPY pyproject.toml README.md ./

# Copy the RAG pipeline and API code.
COPY src/ ./src/
COPY api/ ./api/

# Copy model setup, indexing, PDF preview, and terminal entry points.
COPY setup_models.py ingest.py preview.py ask.py ./

# Register the src package while preserving the project's folder layout.
RUN python -m pip install --no-cache-dir -e .

# Create directories where persistent data and notes will be mounted.
RUN mkdir -p /app/data /app/notes


# Copy the Linux runtime installer into the image.
COPY docker/install_runtime.py /tmp/install_runtime.py

# Tell the RAG configuration where the Linux runtime is installed.
ENV LLM_RUNTIME_DIR=/opt/llama

# Install the runtime and verify that its executable can start.
RUN python /tmp/install_runtime.py \
    && "$(find /opt/llama -type f -name llama-server -print -quit)" --version

    # Include the model preparation command for first-time Docker setup.
COPY docker/prepare_models.py ./docker/prepare_models.py
# Document the backend API port.
EXPOSE 8000

# Start one API worker to avoid loading duplicate local models.
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]