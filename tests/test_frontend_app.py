# Purpose: verify UI controls and reruns using the Streamlit test runner.
# Work: check dynamic weeks, answer rendering, duplicate-request prevention, and offline states.

import unittest
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from frontend.api_client import ApiError

APP = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
LIBRARY = {"documents": [{"source": "Week_16_Notes.pdf", "week": 16}],
           "pdf_count": 1, "page_count": 2, "chunk_count": 3, "index_status": "ready"}


class FrontendAppTests(unittest.TestCase):
    def setUp(self):
        # Start each scenario with fresh metadata rather than a cached generated answer.
        st.cache_data.clear()

    def submit_button(self, app):
        return next(button for button in app.button if button.label == "Ask my notes")

    def test_new_week_answer_and_rerun_do_not_repeat_request(self):
        answer = {"question": "Explain quadrature", "answer": r"Test formula \(x^2\) [1]",
                  "mode": "local_rag", "sources": [{"id": 1, "source": "Week_16_Notes.pdf", "page": 2}]}
        with patch("frontend.api_client.fetch_library", return_value=LIBRARY), \
             patch("frontend.api_client.ask_notes", return_value=answer) as ask:
            app = AppTest.from_file(APP, default_timeout=20).run()
            self.assertEqual(len(app.exception), 0)
            app.selectbox[0].set_value(16).run()
            app.text_area[0].input("Explain quadrature")
            self.submit_button(app).click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any("$x^2$" in item.value for item in app.markdown))
            self.assertTrue(any("PDF page 2" in item.value for item in app.text))
            self.assertEqual(ask.call_args.args[1], 16)
            # Sidebar reruns must preserve the displayed answer without repeating generation.
            app.slider[0].set_value(3).run()
            self.assertEqual(ask.call_count, 1)

    def test_disconnected_backend_disables_submission(self):
        with patch("frontend.api_client.fetch_library", side_effect=ApiError("Cannot reach the backend")):
            app = AppTest.from_file(APP, default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(self.submit_button(app).disabled)
        self.assertIn("Cannot reach", app.error[0].value)

    def test_changed_notes_require_indexing(self):
        stale = dict(LIBRARY, index_status="stale", message="PDFs changed")
        with patch("frontend.api_client.fetch_library", return_value=stale):
            app = AppTest.from_file(APP, default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(self.submit_button(app).disabled)
        self.assertTrue(any("indexing" in message.value for message in app.warning))

    def test_blank_question_does_not_call_backend(self):
        with patch("frontend.api_client.fetch_library", return_value=LIBRARY), \
             patch("frontend.api_client.ask_notes") as ask:
            app = AppTest.from_file(APP, default_timeout=20).run()
            app.text_area[0].input("   ")
            self.submit_button(app).click().run()
        self.assertEqual(len(app.exception), 0)
        ask.assert_not_called()
        self.assertTrue(any("Write a question" in message.value for message in app.error))
