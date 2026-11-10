# Purpose: provide the Numerical Analysis RAG browser interface in Python.
# Work: collect questions and filters, call FastAPI, and display answers, formulas, and references.

import re
import sys
from pathlib import Path

import streamlit as st

# Resolve the frontend package independently of the current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frontend.api_client import ApiError, api_url, ask_notes, fetch_library


@st.cache_data(ttl=10, show_spinner=False)
def cached_library(base_url):
    # Cache library metadata for 10 seconds; generated answers are not cached here.
    return fetch_library(base_url)


def format_math(text):
    # Convert model-generated LaTeX delimiters to the dollar delimiters supported by Streamlit.
    # Preserve the numbers, signs, and mathematical content inside each formula.
    text = re.sub(r"\\\[(.*?)\\\]", lambda match: "\n\n$$\n" + match.group(1) + "\n$$\n\n", text, flags=re.S)
    return re.sub(r"\\\((.*?)\\\)", lambda match: "$" + match.group(1) + "$", text, flags=re.S)


def render_result(saved):
    result = saved["result"]
    st.divider()
    st.subheader("Your answer")
    scope = f"Week {saved['week']}" if saved["week"] else "All notes"
    st.caption(f"{scope} · {saved['top_k']} source pages requested")
    st.write(result["question"])
    if result["mode"] == "no_support":
        st.info(result["answer"])
    else:
        st.markdown(format_math(result["answer"]))
    if result.get("truncated"):
        st.warning("The answer reached its length limit. Check the original notes for the complete explanation.")
    if result.get("citation_warning"):
        st.warning("The model did not provide citation numbers. Check the retrieved references below.")
    if result["sources"]:
        with st.expander("PDF references", expanded=True):
            for source in result["sources"]:
                # Numbers match [1], [2], ... in the generated answer.
                st.text(f"[{source['id']}] {source['source']}  ·  PDF page {source['page']}")
            st.caption("Page numbers refer to the PDF file, which may differ from printed slide numbers.")


def main():
    st.set_page_config(page_title="Numerical Analysis · Study Desk", page_icon="📘", layout="wide")
    st.markdown("**NUMERICAL ANALYSIS / STUDY DESK**")
    st.title("Your notes. A clearer answer.")
    st.caption("Ask a numerical analysis question and get an explanation grounded in your PDFs, with page references.")

    base_url = api_url()
    with st.sidebar:
        st.title("Study settings")
        if st.button("Refresh library", use_container_width=True):
            cached_library.clear()
            st.rerun()

    library, connection_error = None, None
    try:
        library = cached_library(base_url)
    except ApiError as error:
        connection_error = str(error)

    documents = library["documents"] if library else []
    # Discover week options from the API catalogue without a fixed eight-week limit.
    weeks = sorted({doc["week"] for doc in documents if doc.get("week") is not None})
    with st.sidebar:
        week = st.selectbox("Search scope", [None] + weeks, format_func=lambda value: "All notes" if value is None else f"Week {value}")
        top_k = st.slider("Maximum source pages", min_value=1, max_value=10, value=4)
        st.caption("The model includes only the source pages that fit its context window.")
        with st.expander(f"Your PDFs ({len(documents)})"):
            for document in documents:
                st.text(document["source"])
        st.divider()
        st.link_button("API documentation", base_url + "/docs", use_container_width=True)
        st.caption("Answers run locally on your CPU. Each question is independent.")

    ready = bool(library and library["index_status"] == "ready" and documents)
    if connection_error:
        st.error(connection_error)
        st.code(r".\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1", language="powershell")
    elif not ready:
        st.warning("Your notes need indexing before you can ask questions.")
        if library and library.get("message"):
            st.caption(library["message"])
        st.info("Add PDFs to notes/, stop the backend to free model memory, run ingest.py, restart the backend, then refresh the library.")
        st.code(r".\venv\Scripts\python.exe ingest.py", language="powershell")
    else:
        st.success("Backend connected · notes index is ready", icon="✅")

    columns = st.columns(3)
    columns[0].metric("PDFs in your library", len(documents))
    columns[1].metric("Indexed PDF pages", library.get("page_count") if ready else "—")
    columns[2].metric("Searchable chunks", library.get("chunk_count") if ready else "—")

    st.subheader("What would you like to understand?")
    example_columns = st.columns(3)
    for column, label, example in zip(example_columns,
            ["Relative error", "Bisection method", "Jacobi iteration"],
            ["What is relative error and its formula?", "Explain the bisection method and its midpoint formula.", "Explain the Jacobi iterative update formula."]):
        if column.button(label, use_container_width=True, disabled=not ready):
            st.session_state["question_input"] = example

    with st.form("question_form"):
        question = st.text_area("Your question", key="question_input", max_chars=1000, height=120,
            placeholder="For example: Explain the bisection method and its midpoint formula.")
        st.caption("Use a complete question. Clear English course terms work best for retrieval.")
        submitted = st.form_submit_button("Ask my notes", type="primary", use_container_width=True, disabled=not ready)

    if submitted:
        st.session_state.pop("last_result", None)
        st.session_state.pop("last_error", None)
        if not question.strip():
            st.session_state["last_error"] = "Write a question before submitting."
        else:
            try:
                with st.spinner("Searching your notes and generating an answer on your CPU. The first answer may take longer..."):
                    result = ask_notes(question.strip(), week, top_k, base_url)
                st.session_state["last_result"] = {"result": result, "week": week, "top_k": top_k}
            except ApiError as error:
                st.session_state["last_error"] = str(error)

    # Preserve the displayed result across widget reruns without repeating the API request.
    if st.session_state.get("last_error"):
        st.error(st.session_state["last_error"])
    if st.session_state.get("last_result"):
        render_result(st.session_state["last_result"])
    st.divider()
    st.caption("OCR and local models can make mistakes. Verify important formulas against the cited PDF pages.")


if __name__ == "__main__":
    main()
