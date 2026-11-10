# Purpose: verify OCR caching and error-handling guarantees.
# Work: preserve LaTeX, invalidate changed PDFs, and report extraction failures.

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

# Import the project package without downloading OCR models.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag_nm import math_ocr
from rag_nm.table_math import _script_expression


class MathOCRTests(unittest.TestCase):
    def setUp(self):
        # Isolate each test in a temporary directory without modifying original notes or caches.
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pdf = self.root / "notes.pdf"
        self.pdf.write_bytes(b"first PDF content")
        self.engine = Mock()
        self.engine.return_value = SimpleNamespace(markdown=r"$$x^{3}=\frac{a+b}{2}$$")

        # Replace the heavy OCR engine with a test double to isolate cache behavior.
        for mocked in (
            patch.object(math_ocr, "EXTRACTED_DIR", self.root / "cache"),
            patch.object(math_ocr, "_get_engine", return_value=self.engine),
            patch.object(math_ocr, "version", return_value="0.9.11"),
        ):
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_cache_preserves_latex_and_original_page_reference(self):
        first = math_ocr.read_math_page(self.pdf, 3)
        cached = math_ocr.read_math_page(self.pdf, 3)
        self.assertEqual(cached, first)
        self.assertEqual(cached["text"], r"$$x^{3}=\frac{a+b}{2}$$")
        self.assertEqual((cached["source"], cached["page"]), ("notes.pdf", 3))
        self.assertEqual(self.engine.call_count, 1)

    def test_changed_pdf_invalidates_cache(self):
        math_ocr.read_math_page(self.pdf, 1)
        self.pdf.write_bytes(b"updated PDF content")
        self.engine.return_value = SimpleNamespace(markdown=r"$$x^{4}$$")
        updated = math_ocr.read_math_page(self.pdf, 1)
        self.assertEqual(updated["text"], r"$$x^{4}$$")
        self.assertEqual(self.engine.call_count, 2)

    def test_failure_does_not_create_success_cache_or_silent_fallback(self):
        self.engine.side_effect = RuntimeError("OCR failed")
        with self.assertRaisesRegex(RuntimeError, "OCR failed"):
            math_ocr.read_math_page(self.pdf, 1)
        self.assertEqual(list((self.root / "cache").rglob("record.json")), [])


class TableScriptTests(unittest.TestCase):
    def test_script_order_comes_from_positions_not_extraction_order(self):
        # Determine script roles from geometry even when PDF extraction order is reversed.
        spans = [
            {"text": "(k+1)", "size": 7, "origin": (16, 5), "bbox": (16, 0, 35, 7)},
            {"text": "x", "size": 10, "origin": (10, 12), "bbox": (10, 6, 16, 14)},
            {"text": "2", "size": 7, "origin": (16, 16), "bbox": (16, 12, 20, 18)},
        ]
        self.assertEqual(_script_expression(spans, (0, 0, 40, 20)), "x_{2}^{(k+1)}")

    def test_ambiguous_nested_script_is_not_guessed(self):
        spans = [
            {"text": "x", "size": 10, "origin": (10, 15), "bbox": (10, 8, 16, 17)},
            {"text": "1", "size": 7, "origin": (16, 5), "bbox": (16, 0, 20, 7)},
            {"text": "2", "size": 7, "origin": (16, 10), "bbox": (16, 7, 20, 13)},
        ]
        self.assertIsNone(_script_expression(spans, (0, 0, 40, 20)))


if __name__ == "__main__":
    unittest.main()
