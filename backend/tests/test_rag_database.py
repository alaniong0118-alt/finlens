"""Opt-in read-only regression against the existing AAPL dataset; OpenAI is mocked."""
import hashlib
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient
from openai import APITimeoutError, APIConnectionError
from sqlalchemy import select, func

from app.database import SessionLocal
from app.main import app
from app.models import FilingChunk
from app.answer_service import _get_openai_client

ACCESSION = "0000320193-26-000020"
BASE = f"/companies/AAPL/filings/{ACCESSION}"


def database_fingerprint():
    with SessionLocal() as session:
        chunks = session.scalars(select(FilingChunk).order_by(FilingChunk.id)).all()
        serial = [
            {column.name: str(getattr(chunk, column.name))
             for column in FilingChunk.__table__.columns}
            for chunk in chunks
        ]
        total = len(chunks)
        embedded = sum(chunk.embedding is not None for chunk in chunks)
    return total, embedded, hashlib.sha256(json.dumps(serial, sort_keys=True).encode()).hexdigest()


@unittest.skipUnless(os.getenv("FINLENS_RUN_DB_TESTS") == "1", "requires existing local database")
class DatabaseRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = database_fingerprint()
        if cls.before[:2] != (37, 37):
            raise AssertionError(f"Expected existing 37/37 dataset; got {cls.before[:2]}")
        cls.client = TestClient(app)
        # Entire integration suite is unable to create a real provider client.
        cls.provider_patch = patch("app.answer_service._get_openai_client")
        cls.provider = cls.provider_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.provider_patch.stop()
        cls.client.close()
        if database_fingerprint() != cls.before:
            raise AssertionError("Filing rows or embeddings changed during read-only regression")

    def setUp(self):
        self.provider.reset_mock(return_value=True, side_effect=True)

    def provider_response(self, source="source_1"):
        draft = {"claims": [
            {"text": "Products gross margin was $31,525 million.", "citation_ids": [source]},
        ], "insufficient_evidence": False}
        fake = Mock()
        fake.responses.parse.return_value = SimpleNamespace(status="completed", output_parsed=draft)
        self.provider.return_value = fake
        return fake

    def test_health_and_financial_endpoints(self):
        for path in ["/healthz", "/dbz", "/companies"] + [
            f"/companies/{ticker}/{endpoint}" for ticker in ["AAPL", "V"]
            for endpoint in ["financial-summary", "financial-snapshot", "financial-history", "sources"]
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_existing_sources_show_searchable_filings(self):
        apple = self.client.get("/companies/AAPL/sources").json()
        visa = self.client.get("/companies/V/sources").json()
        indexed = [item for item in apple if item["has_filing_chunks"]]
        self.assertEqual([item["accession_number"] for item in indexed], [ACCESSION])
        self.assertTrue(all(not item["has_filing_chunks"] for item in visa))
        self.assertIn("sec_url", apple[0])

    def test_existing_keyword_and_semantic(self):
        for path in ["search", "semantic-search"]:
            response = self.client.get(f"{BASE}/{path}", params={"q": "revenue", "limit": 3})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["result_count"], 3)
            self.assertIn("sec_url", response.json()["results"][0])

    def test_context_hybrid_contract(self):
        data = self.client.get(f"{BASE}/context", params={"q": "gross margin", "limit": 3}).json()
        self.assertEqual(data["evidence_status"], "sufficient")
        self.assertEqual(data["citations"][0]["chunk_id"], "chunk_0018")
        self.assertIn("Gross Margin", data["context"])
        self.assertEqual(len(data["citations"]), 3)
        for citation in data["citations"]:
            self.assertEqual(citation["similarity"], citation["semantic_similarity"])
            self.assertIn("hybrid_score", citation)
            self.assertIn("lexical_score", citation)
        self.provider.assert_not_called()

    def test_answer_complete_flow_mock_provider(self):
        fake = self.provider_response()
        response = self.client.post(f"{BASE}/answer", json={"question": "gross margin", "limit": 3})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["evidence_status"], "sufficient")
        self.assertTrue(data["answer"].endswith("[source_1]"))
        self.assertEqual(data["citations"][0]["accession_number"], ACCESSION)
        self.assertEqual(data["citations"][0]["chunk_id"], "chunk_0018")
        self.assertEqual(data["model"], "gpt-6-astra")
        self.assertTrue({
            "ticker", "company_name", "accession_number", "question", "answer",
            "claims", "citations", "evidence_status", "model",
        }.issubset(data))
        fake.responses.parse.assert_called_once()

    def test_natural_questions_retain_relevant_evidence(self):
        for question, expected in [
            ("What was the gross margin?", "chunk_0018"),
            ("What were the main drivers of services revenue?", "chunk_0018"),
            ("What drove revenue growth?", "chunk_0017"),
            ("How did artificial intelligence affect the business?", "chunk_0019"),
        ]:
            with self.subTest(question=question):
                data = self.client.get(f"{BASE}/context", params={"q": question}).json()
                self.assertEqual(data["evidence_status"], "sufficient")
                self.assertIn(expected, [c["chunk_id"] for c in data["citations"]])
        self.provider.assert_not_called()

    def test_unrelated_question_in_indexed_filing_does_not_call_llm(self):
        response = self.client.post(f"{BASE}/answer", json={
            "question": "What clinical trial results did Apple report?",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["evidence_status"], "insufficient")
        self.assertEqual(response.json()["claims"], [])
        self.provider.assert_not_called()

    def test_unsupported_model_citation_http_502(self):
        self.provider_response("source_99")
        response = self.client.post(f"{BASE}/answer", json={"question": "gross margin"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.headers["X-FinLens-Error-Code"], "MALFORMED_MODEL_OUTPUT")
        self.assertNotIn("answer", response.json())

    def test_provider_failure_and_timeout(self):
        for error, status in [
            (APIConnectionError(message="private-upstream-body", request=httpx.Request("POST", "https://api.openai.com")), 502),
            (APITimeoutError(request=httpx.Request("POST", "https://api.openai.com")), 504),
        ]:
            with self.subTest(status=status):
                fake = self.provider_response()
                fake.responses.parse.side_effect = error
                response = self.client.post(f"{BASE}/answer", json={"question": "gross margin"})
                self.assertEqual(response.status_code, status)
                self.assertEqual(
                    response.headers["X-FinLens-Error-Code"],
                    "UPSTREAM_FAILURE" if status == 502 else "LLM_TIMEOUT",
                )
                self.assertNotIn("private-upstream-body", response.text)

    def test_missing_key_config_http_503(self):
        _get_openai_client.cache_clear()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.provider.side_effect = _get_openai_client
            response = self.client.post(f"{BASE}/answer", json={"question": "gross margin"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["X-FinLens-Error-Code"], "LLM_UNAVAILABLE")
        _get_openai_client.cache_clear()

    def test_no_retrieval_means_no_llm(self):
        path = "/companies/AAPL/filings/not-in-database/answer"
        response = self.client.post(path, json={"question": "revenue growth"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["evidence_status"], "insufficient")
        self.assertEqual(data["claims"], [])
        self.assertEqual(data["citations"], [])
        self.assertIn("model", data)
        self.provider.assert_not_called()

    def test_invalid_input_and_unknown_company(self):
        for body in [{"question": " \n "}, {"question": "revenue", "limit": 51}]:
            self.assertEqual(self.client.post(f"{BASE}/answer", json=body).status_code, 422)
        self.assertEqual(self.client.post(
            "/companies/DOESNOTEXIST/filings/none/answer",
            json={"question": "revenue"},
        ).status_code, 404)
        self.provider.assert_not_called()

    def test_database_dimensions(self):
        with SessionLocal() as session:
            rows = session.execute(select(
                func.vector_dims(FilingChunk.embedding), func.count(),
            ).group_by(func.vector_dims(FilingChunk.embedding))).all()
        self.assertEqual(rows, [(384, 37)])


if __name__ == "__main__":
    unittest.main()
