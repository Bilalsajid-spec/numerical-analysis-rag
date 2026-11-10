# Purpose: connect HTTP requests to the existing RAG pipeline.
# Work: receive questions, reuse the model, and return responses.

from contextlib import asynccontextmanager
from threading import Lock

import requests
from fastapi import FastAPI, HTTPException

from api.schemas import AskRequest, AskResponse, LibraryResponse

# Alias the existing function to distinguish it from the API route handler.
from rag_nm.pipeline import ask as rag_ask
from rag_nm.generation import LocalGenerator
from rag_nm.library import list_documents
from rag_nm.retrieval import load_manifest
# Allow browser API calls from the configured frontend origins.
from fastapi.middleware.cors import CORSMiddleware


# Manage shared resources during API startup and shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the generator; Qwen loads on the first supported question.
    app.state.generator = LocalGenerator()

    # Process one RAG request at a time.
    app.state.rag_lock = Lock()

    try:
        # Serve API requests while the application is running.
        yield
    finally:
        # Close the owned model process and HTTP session on shutdown.
        app.state.generator.close()


# Attach the resource lifecycle manager to the application.
app = FastAPI(
    title="Numerical Analysis RAG API",
    lifespan=lifespan,
)

# Allow the local frontend development origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    # This application currently does not use cookie-based login.
    allow_credentials=False,
    # Use GET for health checks and POST for question requests.
    allow_methods=["GET", "POST"],
    # The frontend uses this header when sending a JSON request body.
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    # Check API liveness; this does not establish model readiness.
    return {
        "status": "ok",
        "service": "Numerical Analysis RAG API",
    }


@app.get("/library", response_model=LibraryResponse)
def library():
    # Read metadata without loading OCR, embedding, or answer models.
    documents = list_documents()
    result = {"documents": documents, "pdf_count": len(documents), "index_status": "ready"}
    try:
        manifest = load_manifest()
        result.update(page_count=manifest["page_count"], chunk_count=manifest["chunk_count"])
    except FileNotFoundError as error:
        result.update(index_status="missing", message=str(error))
    except ValueError as error:
        result.update(index_status="stale", message=str(error))
    return result


# Validate and filter outgoing data using the response model.
@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest):
    try:
        # Allow only one request to use the shared RAG resources at a time.
        with app.state.rag_lock:
            result = rag_ask(
                question=payload.question,
                generator=app.state.generator,
                top_k=payload.top_k,
                week=payload.week,
            )

    except ValueError as error:
        # For example, the saved index may no longer match the current PDFs.
        raise HTTPException(
            status_code=409, detail=str(error)
        ) from error

    except requests.Timeout as error:
        # The local model did not respond within the allowed time.
        raise HTTPException(
            status_code=504,
            detail="Local model response timed out.",
        ) from error

    except (OSError, RuntimeError, requests.RequestException) as error:
        # A model or index is missing, or the local service is unavailable.
        raise HTTPException(
            status_code=503, detail=str(error)
        ) from error

    # Report model-format, citation, and context failures as errors.
    if result["mode"] not in {"local_rag", "no_support"}:
        raise HTTPException(
            status_code=502,
            detail={
                "code": result["mode"],
                "message": result["answer"],
            },
        )

    # Convert the internal RAG result into the frontend response format.
    return {
        "question": result["question"],
        "answer": result["answer"],
        "mode": result["mode"],
        "sources": [
            {
                "id": number,
                "source": item["source"],
                "page": item["page"],
            }
            for number, item in enumerate(result["sources"], start=1)
        ],
        "best_similarity": result.get("best_similarity"),
        "truncated": result.get("truncated", False),
        "citation_warning": result.get("citation_warning", False),
    }
