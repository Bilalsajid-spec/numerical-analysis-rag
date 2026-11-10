# Purpose: handle HTTP communication between the Python frontend and FastAPI.
# Work: fetch library metadata and answers, and present readable API errors.

import os

import requests


class ApiError(Exception):
    """Provide readable errors when the API is unavailable or its response is invalid."""


def api_url():
    # Use this setting to change the backend address in other deployment environments.
    return os.getenv("RAG_API_URL", "http://127.0.0.1:8000").rstrip("/")


def _error_message(detail):
    # FastAPI validation errors may be lists; service errors may be strings or dictionaries.
    if isinstance(detail, list):
        return "; ".join(
            f"{'.'.join(str(part) for part in item.get('loc', []))}: {item.get('msg', 'Invalid input')}"
            for item in detail if isinstance(item, dict)
        ) or "The API rejected the request."
    if isinstance(detail, dict):
        return str(detail.get("message", detail.get("code", "The API could not complete the request.")))
    return str(detail or "The API could not complete the request.")


def _request(method, path, payload=None, base_url=None):
    url = (base_url or api_url()).rstrip("/") + path
    try:
        # Send the request from the Python frontend server rather than directly from the browser.
        with requests.Session() as session:
            session.trust_env = False
            response = session.request(
                method, url, json=payload,
                # Allow time for CPU model startup and generation; keep metadata requests short.
                timeout=(3, 300 if method == "POST" else 10),
            )
    except requests.Timeout as error:
        raise ApiError("The backend took too long. Check its terminal before submitting again; CPU generation may still be running.") from error
    except requests.ConnectionError as error:
        raise ApiError("Cannot reach the backend. Start the FastAPI server on port 8000, then refresh the library.") from error
    except requests.RequestException as error:
        raise ApiError(f"Could not contact the backend: {error}") from error

    try:
        data = response.json()
    except ValueError as error:
        raise ApiError(f"The backend returned a non-JSON response (HTTP {response.status_code}).") from error
    if not response.ok:
        detail = data.get("detail") if isinstance(data, dict) else data
        raise ApiError(f"HTTP {response.status_code}: {_error_message(detail)}")
    if not isinstance(data, dict):
        raise ApiError("The backend returned an unexpected response format.")
    return data


def fetch_library(base_url=None):
    data = _request("GET", "/library", base_url=base_url)
    if data.get("index_status") not in {"ready", "missing", "stale"} or not isinstance(data.get("documents"), list):
        raise ApiError("Library metadata is invalid. Restart the updated FastAPI backend.")
    return data


def ask_notes(question, week=None, top_k=4, base_url=None):
    # Send a JSON POST request without importing RAG or model code into the frontend.
    data = _request("POST", "/ask", {"question": question, "week": week, "top_k": top_k}, base_url)
    if data.get("mode") not in {"local_rag", "no_support"} or not isinstance(data.get("answer"), str) or not isinstance(data.get("sources"), list):
        raise ApiError("The backend returned an invalid answer format.")
    return data
