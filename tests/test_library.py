# Purpose: verify additional PDF weeks and dynamic document discovery.
# Work: test Week 16 filtering, missing selections, and catalogue responses without models.

import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from api.main import app
from rag_nm import library, retrieval


class LibraryTests(unittest.TestCase):
    def test_discovers_new_weeks_and_unnumbered_notes(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ["Week_1_Numerical_Analysis.pdf", "Week_16_Numerical_Analysis.pdf", "Extra_notes.pdf", "ignore.txt"]:
                (Path(folder) / name).write_bytes(b"test file")
            with patch.object(library, "NOTES_DIR", Path(folder)):
                documents = library.list_documents()
        self.assertEqual({item["source"]: item["week"] for item in documents}, {
            "Week_1_Numerical_Analysis.pdf": 1, "Week_16_Numerical_Analysis.pdf": 16, "Extra_notes.pdf": None,
        })

    def test_week_16_retrieval_uses_its_actual_source(self):
        source = "Week_16_Numerical_Analysis.pdf"
        chunk = {"id": "new", "source": source, "page": 1, "title": "Quadrature", "text": "quadrature formula"}
        collection = Mock()
        collection.query.return_value = {"ids": [["new"]], "distances": [[0.1]]}
        client = Mock()
        client.get_collection.return_value = collection
        manifest = {"collection": "test", "chunks_file": "chunks.json", "pages_file": "pages.json"}
        lexical = ([chunk], [Counter({"quadrature": 1, "formula": 1})], Counter({"quadrature": 1, "formula": 1}), [2], 2)
        with patch.object(retrieval, "load_manifest", return_value=manifest), \
             patch.object(retrieval, "list_documents", return_value=[{"source": source, "week": 16}]), \
             patch.object(retrieval, "_lexical_index", return_value=lexical), \
             patch.object(retrieval, "_parent_pages", return_value={}), \
             patch.object(retrieval, "db_client", return_value=client), \
             patch.object(retrieval, "encode", return_value=[[1.0]]):
            result = retrieval.retrieve("quadrature", week=16)
        self.assertTrue(result["supported"])
        self.assertEqual(result["hits"][0]["source"], source)
        self.assertEqual(collection.query.call_args.kwargs["where"], {"source": {"$in": [source]}})
        self.assertEqual(collection.query.call_args.kwargs["n_results"], 1)

    def test_missing_week_fails_before_embedding(self):
        manifest = {"chunks_file": "test"}
        with patch.object(retrieval, "load_manifest", return_value=manifest), \
             patch.object(retrieval, "_lexical_index", return_value=([], [], Counter(), [], 0)), \
             patch.object(retrieval, "list_documents", return_value=[]), \
             patch.object(retrieval, "encode") as encode:
            with self.assertRaisesRegex(ValueError, "No PDF found for week 16"):
                retrieval.retrieve("quadrature", week=16)
        encode.assert_not_called()

    def test_api_accepts_week_16(self):
        result = {"question": "quadrature", "answer": "No support", "mode": "no_support", "sources": []}
        with TestClient(app) as client, patch("api.main.rag_ask", return_value=result) as rag:
            response = client.post("/ask", json={"question": "quadrature", "week": 16})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rag.call_args.kwargs["week"], 16)

    def test_library_reports_stale_index_without_starting_model(self):
        with TestClient(app) as client, \
             patch("api.main.list_documents", return_value=[{"source": "Week_16_Notes.pdf", "week": 16}]), \
             patch("api.main.load_manifest", side_effect=ValueError("PDFs changed. Run ingest.py.")), \
             patch("api.main.LocalGenerator.start") as start:
            response = client.get("/library")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["index_status"], "stale")
        self.assertIsNone(response.json()["page_count"])
        self.assertEqual(response.json()["documents"][0]["week"], 16)
        start.assert_not_called()
