# Run Numerical Analysis RAG with Docker

This project runs a Streamlit frontend and a FastAPI RAG backend
in separate Linux containers. Answer generation uses a local CPU model.

## Requirements

- Docker with support for Linux x64 containers.
- Internet access for initial image and model downloads.
- Sufficient disk space and RAM for dependencies and local models.
- Your numerical analysis PDF notes.

Host Python, a virtual environment, and Node.js are not required
for the Docker workflow.

## 1. Get the project

Download and extract the repository, or clone it.

Open a terminal in the project root: the folder containing
Dockerfile and compose.yaml.


M## 2. Pull the published images

Make sure the Docker engine is running.

```powershell
docker compose pull
```

This downloads the frontend and backend images from Docker Hub:

- bill55/numerical-analysis-rag-frontend:1.0.0
- bill55/numerical-analysis-rag-backend:1.0.0

Building images locally is not required for this setup.
The images do not contain your PDF notes or model weights;
prepare those in the following steps.
## 3. Prepare model weights

```powershell
docker compose run --rm --no-deps backend python docker/prepare_models.py
```

This prepares MiniLM embedding files and the Qwen answer model.

Weights are saved in the host's data/models/ folder through a bind
mount. The temporary container is removed after completion;
the downloaded files remain.

The Linux inference runtime is already installed in the backend image.

## 4. Add your PDFs

Place PDFs directly inside notes/, without creating subfolders.

Example:

```text
notes/
├── Week_1_Numerical_Analysis.pdf
├── Week_2_Numerical_Analysis.pdf
└── My_Notes.pdf
```

The Week_<number>_ filename pattern enables week filters.
Other .pdf filenames remain searchable under All notes.

Use unique filenames. Original course PDFs are not included
in the repository.

## 5. Build the search index

```powershell
docker compose run --rm --no-deps backend python ingest.py
```

Missing OCR models download when uncached pages are processed.
Valid OCR caches are reused.

The Docker search index is stored in a persistent named volume,
separate from any native Windows index.

Successful ingestion prints a READY message with PDF, page,
and chunk counts.

## 6. Start the application

Stop any existing application using ports 8000 or 5173, then run:

```powershell
docker compose up -d --wait
```

Open:

- Frontend: http://127.0.0.1:5173
- API documentation: http://127.0.0.1:8000/docs

Check that the library reports ready, then ask a question.

The answer model loads on the first supported question.
Health checks confirm service liveness, not answer correctness.

## 7. Add or change PDFs later

Stop the services:

```powershell
docker compose down
```

Update the files in notes/, then run:

```powershell
docker compose run --rm --no-deps backend python ingest.py
docker compose up -d --wait
```

Refresh the library in the frontend.

## 8. Stop and inspect services

```powershell
docker compose down
docker compose ps
docker compose logs --tail 100 backend frontend
```

Normal docker compose down preserves the named volume and
host-mounted PDFs, model weights, and OCR cache.

Removing the named volume explicitly deletes Docker's generated
index and requires ingestion again.

## Where processing happens

Containers run on the machine where Docker is running.
That machine supplies the CPU, RAM, and disk.

The frontend calls the backend through Docker networking.
Qwen runs inside the backend container; no paid answer API is used.