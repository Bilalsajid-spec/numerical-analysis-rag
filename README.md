<!-- Purpose: provide the quickest verified way to run this local RAG project. -->
<!-- Work: keep setup, commands, architecture, and verification pointers easy to find. -->

# Numerical Analysis RAG

A fully local study assistant for numerical analysis PDFs in `notes/`. It includes a Python Streamlit frontend, a FastAPI backend, local retrieval, and a quantized Qwen answer model with PDF/page sources. The original eight PDFs contain 109 pages; more PDFs can be indexed.

**Detailed beginner-friendly explanation:** [EXPLAIN_PROJECT.md](EXPLAIN_PROJECT.md).

The original local index has **8 PDFs, 109 pages, 341 chunks**. The current automated suite has **32 tests**, and the original retrieval/refusal evaluation passed **12/12** examples. PDFs, models and generated results are not included in the repository. These checks do not establish correctness of every possible answer.

## Requirements and fresh checkout

The full application/model setup currently targets **Windows x64**. Development was verified with **Python 3.14.5**, CPU inference, and approximately 8 GB installed RAM. Model downloads and installed dependencies need several GB of disk space. Other operating systems need an adapted llama.cpp runtime; Docker support is not included yet.

Clone the GitHub repository, open its root folder, then run:

```powershell
py -3.14 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# Make the src/rag_nm package importable by the API and tests.
.\venv\Scripts\python.exe -m pip install -e .
.\venv\Scripts\python.exe setup_models.py
```

Copy your PDFs into `notes/` using the [notes guide](notes/README.md), then build the index:

```powershell
.\venv\Scripts\python.exe ingest.py
```

Initial setup requires internet. Once models and the index are ready, questions use local inference without a paid API key. `setup_models.py` downloads pinned Qwen/runtime artifacts and checks their hashes. Application direct dependencies are version-pinned in `requirements.txt`; transitive dependencies are resolved by pip.

## Browser app (Python only)

No Node.js or npm is needed. Install dependencies with the venv command below, then use two terminals from the project root.

Terminal 1 - RAG API:

```powershell
.\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Terminal 2 - Streamlit frontend:

```powershell
.\venv\Scripts\python.exe -m streamlit run frontend/app.py --server.port 5173 --server.address 127.0.0.1
```

Open **http://127.0.0.1:5173**. The UI calls `GET /library` for PDFs/index status and sends JSON to `POST /ask`. The backend performs retrieval and calls local Qwen on port 8765. The frontend imports no RAG/model code. `RAG_API_URL` optionally changes its backend address; default is `http://127.0.0.1:8000`.

The UI displays formulas, numbered PDF/page references, loading state, refusals, and service errors. Its displayed answer survives widget reruns without reissuing the question. Questions are independent; there is no conversational model memory. API docs: **http://127.0.0.1:8000/docs**.

## Add more PDFs / weeks

1. Stop the API (`Ctrl+C`) to release Qwen memory before OCR/indexing.
2. Copy additional PDFs into `notes/`. Use unique filenames. `Week_9_Numerical_Analysis.pdf` through `Week_16_Numerical_Analysis.pdf` will get week filters automatically. Other PDF names are included under **All notes**.
3. Run `.\venv\Scripts\python.exe ingest.py`. Existing unchanged page OCR is reused; new/changed PDFs need OCR, and the complete vector index is rebuilt.
4. Restart the API and click **Refresh library** in the frontend. No answer-model retraining or model re-download is needed.

Adding/deleting/changing PDFs makes the old index stale; answering is disabled until ingestion succeeds. More pages take more disk/indexing time, and retrieval quality should be evaluated on the new material. The original 12-example evaluation only covers the original weeks.

## Terminal interface

After setup/indexing, you can also ask questions without the browser app:

```powershell
.\venv\Scripts\python.exe ask.py "Explain the bisection method and its midpoint formula."
.\venv\Scripts\python.exe ask.py
```

The second command starts interactive questions; type `exit` to close. Questions are independent, without persistent conversational memory. Use clear English course terms for best retrieval.

## Other commands

```powershell
.\venv\Scripts\python.exe ask.py "Explain Jacobi" --week 8 --retrieve-only
.\venv\Scripts\python.exe ask.py "What is relative error?" --json
.\venv\Scripts\python.exe preview.py --pdf Week_8_Numerical_Analysis.pdf --page 3 --full
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\venv\Scripts\python.exe evaluate.py --generate
```

`evaluate.py --generate` writes actual local answers to `DEMO_OUTPUT.md`, and retrieval/refusal metrics to `data/evaluation.json`. These generated files stay local.

## Data flow

```text
PDFs -> local math OCR -> page cache -> protected chunks -> MiniLM vectors -> Chroma
Question -> vector + keyword search -> matching parent pages -> local Qwen -> answer + sources
```

OCR runs in a child process before indexing, freeing its models before embedding. Answer generation uses a hidden CPU-only llama.cpp child process bound to `127.0.0.1`; the app closes its own child process when the session ends.

## Rebuilds and settings

- Changed PDFs: run `ingest.py` again.
- Recompute vectors from cached OCR: `ingest.py --rebuild`.
- Recompute all OCR too: `ingest.py --refresh-ocr`.
- Optional settings: copy `.env.example` to `.env` and adjust CPU threads, local port, or retrieval cutoff.
- First downloads need internet. After local models and page caches are prepared, no paid API key is needed.

New index collections become active only after a successful build. Changed PDFs/embedding weights trigger a rebuild message rather than silently using stale vectors.

## Accuracy and verification

All eight original PDFs were extracted; extraction is distinct from validating every formula. Main formulas on three sample pages were compared against the original PDFs. The local report is `data/formula_review.md`; generated reports and course material are excluded from Git. OCR and the small local language model can still make mistakes. Check important mathematics against the cited original page.

Long equations remain intact in stored text. An equation longer than the embedding model's input limit may have a truncated vector representation; full-text keyword search still uses the complete stored text. Unsupported questions are screened before generation, but this heuristic is not a perfect relevance detector.

The project's code includes explanatory English comments. Detailed file purposes, source references, models, cache behavior, hardware considerations, and troubleshooting are in [EXPLAIN_PROJECT.md](EXPLAIN_PROJECT.md).

## API contract

`GET /health` checks API liveness. `GET /library` returns discovered PDFs and index status. `POST /ask` accepts:

```json
{"question": "Explain the bisection method", "week": 6, "top_k": 4}
```

`question` is required (1-1000 characters after trimming). `week` is optional and positive; `top_k` defaults to 4 and is limited to 1-10. A normal response contains `question`, `answer`, `mode`, `sources` (`id`, `source`, `page`), `best_similarity`, `truncated`, and `citation_warning`. `best_similarity` is a retrieval score, not an answer-correctness probability.

HTTP 200 can represent `local_rag` or `no_support`. Invalid input uses 422; stale index/selection problems use 409; invalid model output uses 502; unavailable local resources use 503; model request timeout uses 504. `/docs` provides interactive documentation and `/openapi.json` the API specification.

This is a loopback development application. It currently has no user authentication and is not configured for public internet hosting. CORS settings are browser-origin settings, not access control.

## Tests and GitHub Actions

To run the mocked automated suite without downloading OCR/embedding/answer models or needing private PDFs, start with an empty venv and install the CI dependencies instead of the full application requirements:

```powershell
py -3.14 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-ci.txt
.\venv\Scripts\python.exe -m pip install --no-build-isolation -e .
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

`.github/workflows/tests.yml` runs these checks on Windows/Python 3.14 for pushes and pull requests. Mocked tests cover API validation/output/errors, frontend HTTP requests and UI reruns, Week 16 filtering, formula preservation, OCR caching, and failed-index rollback. Real retrieval/model evaluation still requires local PDFs/models/index and is run separately with `evaluate.py`.

## Repository layout

```text
.github/workflows/tests.yml  Automated CI checks
.streamlit/config.toml       Local frontend appearance/port
api/                        HTTP routes and request/response schemas
frontend/                   Python UI and HTTP client
src/rag_nm/                 Reusable RAG pipeline modules
tests/                      Model-free automated tests
examples/questions.json     Original retrieval evaluation questions
notes/README.md             Instructions for adding local PDFs
setup_models.py             Download local model/runtime files
ingest.py                   Build the index
ask.py                      CLI questions
preview.py                  Inspect PDF extraction
evaluate.py                 Real retrieval/answer evaluation
requirements.txt            Full application direct dependencies
requirements-ci.txt         Lightweight test dependencies
pyproject.toml              Python package build metadata
```

`venv/`, `data/`, original notes, `.env`, local secrets, model binaries and generated reports stay on the machine through `.gitignore`. A clone needs its own setup and notes. [GitHub publishing instructions](GITHUB_SETUP.md) explain the first commit and push.

No project-wide distribution license has been selected yet. Downloaded libraries, model weights, and runtime binaries retain their own licenses; those artifacts are not redistributed in this repository.
