# Purpose: check important RAG failure modes and formula preservation.
# Work: test protected math, page boundaries, atomic rollback, refusals, and citation errors.

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag_nm.chunking import chunk_pages
from rag_nm.generation import LocalGenerator, formula_source_ids
from rag_nm.pipeline import ask
from rag_nm import retrieval


class ChunkTests(unittest.TestCase):
    def test_formulas_stay_whole_and_pages_do_not_mix(self):
        formula = r"$$x_i^{(k+1)} = \frac{1}{a_{ii}} (b_i-\sum_{j\ne i}a_{ij}x_j^{(k)})$$"
        pages = [{"source": "week.pdf", "page": 1, "text": "Many introductory words " * 10 + formula},
                 {"source": "week.pdf", "page": 2, "text": "SECOND_PAGE_ONLY"}]
        chunks = chunk_pages(pages, lambda text: len(text.split()), 10, 2)
        self.assertTrue(any(formula in chunk["text"] for chunk in chunks))
        self.assertTrue(all("SECOND_PAGE_ONLY" not in c["text"] for c in chunks if c["page"] == 1))
        self.assertEqual(len({c["id"] for c in chunks}), len(chunks))

    def test_table_rows_keep_headers_and_values(self):
        page = {"source": "a.pdf", "page": 3, "text": "<table><tr><td>x</td><td>f(x)</td></tr><tr><td>1</td><td>2</td></tr><tr><td>3</td><td>4</td></tr></table>"}
        result = chunk_pages([page], lambda text: len(text.split()), 30, 0)
        text = " ".join(c["text"] for c in result)
        self.assertIn("Table columns: x | f(x)", text)
        self.assertIn("Table row: 1 | 2", text)
        self.assertIn("Table row: 3 | 4", text)

    def test_oversize_equation_is_not_cut_or_lost(self):
        formula = "$$" + " + ".join("x" for _ in range(50)) + "$$"
        chunks = chunk_pages([{"source": "a.pdf", "page": 1, "text": formula}], lambda text: len(text.split()), 10, 2)
        self.assertEqual(chunks[0]["text"], formula)
        self.assertTrue(chunks[0]["oversize_atomic"])


class ReliabilityTests(unittest.TestCase):
    def test_exact_formula_match_adds_its_actual_source(self):
        answer = r"\[x_i^{(k+1)} = \frac{1}{a_{ii}} b_i\]"
        sources = [{"text": "Jacobi uses the previous iteration."},
                   {"text": r"$$x _ { i } ^ { ( k + 1 ) } = \frac { 1 } { a _ { i i } } b _ { i } .$$"}]
        self.assertEqual(formula_source_ids(answer, sources), [2])

    def test_unsupported_question_never_calls_language_model(self):
        generator = Mock()
        with patch("rag_nm.pipeline.retrieve", return_value={"supported": False, "hits": [], "best_similarity": 0.1}):
            result = ask("tomorrow weather?", generator)
        generator.generate.assert_not_called()
        self.assertEqual(result["mode"], "no_support")

    def test_invalid_generated_citations_are_rejected(self):
        generator = LocalGenerator()
        generator.start = Mock()
        def response(route, body=None, timeout=180):
            if route == "/apply-template":
                return {"prompt": "test"}
            if route == "/tokenize":
                return {"tokens": [1,2,3]}
            return {"choices": [{"message": {"content": json.dumps({"answer": "Unverifiable assertion [99]", "citations": [99]})}, "finish_reason": "stop"}]}
        generator._request = response
        result = generator.generate("bisection?", [{"source": "week.pdf", "page": 3, "text": "Midpoint divides the interval."}])
        self.assertEqual(result["mode"], "citation_error")

    def test_failed_rebuild_preserves_active_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "manifest.json"
            manifest.write_text('{"collection":"previous"}', encoding="utf-8")
            collection = Mock()
            collection.add.side_effect = RuntimeError("database add failed")
            client = Mock()
            client.create_collection.return_value = collection
            chunk = {"id": "1", "text": "sample", "title": "sample", "source": "a.pdf", "page": 1, "part": 0, "review_required": True, "oversize_atomic": False}
            with patch.object(retrieval, "INDEX_MANIFEST", manifest), patch.object(retrieval, "db_client", return_value=client), patch.object(retrieval, "encode", return_value=[[1.0,0.0]]):
                with self.assertRaisesRegex(RuntimeError, "database add failed"):
                    retrieval.save_index([chunk], 1, "test")
            self.assertEqual(json.loads(manifest.read_text())["collection"], "previous")
            client.delete_collection.assert_called_once()


if __name__ == "__main__":
    unittest.main()
