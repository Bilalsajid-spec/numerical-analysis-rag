# Purpose: verify the API contract and error handling.
# Work: test endpoints with controlled results without running a real language model.

import unittest
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

from api.main import app


class ApiTests(unittest.TestCase):
    def test_answer_response(self):
        # Use a controlled fixture instead of an actual model-generated answer.
        fake_result = {
            "question": "Explain bisection",
            "answer": "Test answer [1]",
            "mode": "local_rag",
            "sources": [
                {
                    "source": "Week_6_Numerical_Analysis.pdf",
                    "page": 3,
                    "text": "Internal page text",
                }
            ],
            "best_similarity": 0.7,
        }

        with TestClient(app) as client:
            with patch("api.main.rag_ask", return_value=fake_result):
                response = client.post(
                    "/ask", json={"question": "Explain bisection"}
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "local_rag")
        self.assertEqual(body["sources"][0]["id"], 1)
        self.assertNotIn("text", body["sources"][0])
        self.assertFalse(body["truncated"])

    def test_refusal_response(self):
        fake_result = {
            "question": "Unrelated question",
            "answer": "No supporting notes found.",
            "mode": "no_support",
            "sources": [],
        }

        with TestClient(app) as client:
            with patch("api.main.rag_ask", return_value=fake_result):
                response = client.post(
                    "/ask", json={"question": "Unrelated question"}
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "no_support")
        self.assertEqual(response.json()["sources"], [])

    def test_invalid_input_skips_rag(self):
        invalid_bodies = [
            {},
            {"question": "   "},
            {"question": "Explain error", "week": 0},
            {"question": "Explain error", "top_k": 0},
        ]

        with TestClient(app) as client:
            with patch("api.main.rag_ask") as mocked_rag:
                for body in invalid_bodies:
                    with self.subTest(body=body):
                        response = client.post("/ask", json=body)
                        self.assertEqual(response.status_code, 422)

                # Invalid input must be rejected before calling the expensive RAG function.
                mocked_rag.assert_not_called()

    def test_service_errors(self):
        cases = [
            (ValueError("Index outdated"), 409),
            (FileNotFoundError("Model missing"), 503),
            (requests.Timeout("Timed out"), 504),
        ]

        with TestClient(app) as client:
            for error, expected_status in cases:
                with self.subTest(error=type(error).__name__):
                    with patch("api.main.rag_ask", side_effect=error):
                        response = client.post(
                            "/ask", json={"question": "Explain error"}
                        )

                    self.assertEqual(response.status_code, expected_status)

    def test_invalid_model_output(self):
        fake_result = {
            "mode": "citation_error",
            "answer": "Invalid source numbers.",
        }

        with TestClient(app) as client:
            with patch("api.main.rag_ask", return_value=fake_result):
                response = client.post(
                    "/ask", json={"question": "Explain error"}
                )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"]["code"], "citation_error"
        )
