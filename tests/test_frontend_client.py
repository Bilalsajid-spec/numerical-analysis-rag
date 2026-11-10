# Purpose: verify the frontend HTTP contract and readable error messages.
# Work: check POST bodies, timeouts, refusals, and API validation errors.

import unittest
from unittest.mock import Mock, patch

import requests

from frontend.api_client import ApiError, ask_notes, fetch_library


class FrontendClientTests(unittest.TestCase):
    def session(self, factory, payload, status=200):
        session = factory.return_value.__enter__.return_value
        session.request.return_value = Mock(status_code=status, ok=status < 400)
        session.request.return_value.json.return_value = payload
        return session

    @patch("frontend.api_client.requests.Session")
    def test_question_is_sent_over_http_with_new_week(self, factory):
        answer = {"question": "Explain quadrature", "answer": "Example", "mode": "local_rag", "sources": []}
        session = self.session(factory, answer)
        self.assertEqual(ask_notes("Explain quadrature", 16, 3, "http://127.0.0.1:8000/"), answer)
        session.request.assert_called_once_with("POST", "http://127.0.0.1:8000/ask",
            json={"question": "Explain quadrature", "week": 16, "top_k": 3}, timeout=(3, 300))
        self.assertFalse(session.trust_env)

    @patch("frontend.api_client.requests.Session")
    def test_validation_error_is_readable(self, factory):
        self.session(factory, {"detail": [{"loc": ["body", "question"], "msg": "Required"}]}, 422)
        with self.assertRaisesRegex(ApiError, "HTTP 422: body.question: Required"):
            ask_notes("")

    @patch("frontend.api_client.requests.Session")
    def test_model_error_dict_is_readable(self, factory):
        self.session(factory, {"detail": {"code": "citation_error", "message": "Invalid citations"}}, 502)
        with self.assertRaisesRegex(ApiError, "Invalid citations"):
            ask_notes("question")

    @patch("frontend.api_client.requests.Session")
    def test_timeout_is_not_retried_automatically(self, factory):
        session = factory.return_value.__enter__.return_value
        session.request.side_effect = requests.Timeout()
        with self.assertRaisesRegex(ApiError, "too long"):
            ask_notes("question")
        self.assertEqual(session.request.call_count, 1)

    @patch("frontend.api_client.requests.Session")
    def test_disconnected_backend_is_explained(self, factory):
        session = factory.return_value.__enter__.return_value
        session.request.side_effect = requests.ConnectionError()
        with self.assertRaisesRegex(ApiError, "Start the FastAPI server"):
            fetch_library()

    @patch("frontend.api_client.requests.Session")
    def test_unexpected_answer_is_rejected(self, factory):
        self.session(factory, {"message": "Old echo endpoint"})
        with self.assertRaisesRegex(ApiError, "invalid answer format"):
            ask_notes("question")
