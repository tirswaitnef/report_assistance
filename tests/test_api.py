import importlib
import os
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.engine import make_context, template_generate
from app.models import GeneratedOutput, ReportRequest
from tests.test_domain import sample_case


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory(prefix="db-report-test-")
        with patch.dict(os.environ, {"DB_REPORT_DATA_DIR": cls.storage.name}):
            cls.main = importlib.import_module("app.main")
        cls.client_context = TestClient(cls.main.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        cls.storage.cleanup()

    def report_count(self):
        with sqlite3.connect(self.main.DB_PATH) as connection:
            return connection.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

    def create(self, **overrides):
        payload = {"case": sample_case(), "grounding": True, "rag": True, "provider": "template"}
        payload.update(overrides)
        return self.client.post("/api/reports", json=payload)

    def test_health_and_corpus_are_usable(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        health = response.json()
        self.assertEqual(health["status"], "ok")
        self.assertGreater(health["case_count"], 0)
        self.assertGreater(health["corpus_chunks"], 0)
        self.assertFalse(health["semantic_validation"])
        knowledge = self.client.get("/api/knowledge")
        self.assertEqual(knowledge.status_code, 200)
        self.assertEqual(len(knowledge.json()["sources"]), 4)
        self.assertEqual(knowledge.json()["license"], "CC-BY-SA-4.0")

    def test_all_sample_cases_can_generate_reports(self):
        response = self.client.get("/api/cases")
        self.assertEqual(response.status_code, 200)
        cases = response.json()
        self.assertTrue(cases)
        for case in cases:
            with self.subTest(case=case["id"]):
                detail = self.client.get(f"/api/cases/{case['id']}")
                self.assertEqual(detail.status_code, 200)
                generated = self.create(case=detail.json())
                self.assertEqual(generated.status_code, 201, generated.text)
                self.assertEqual(generated.json()["summary"]["total"], case["finding_count"])

    def test_create_persist_read_export_and_evaluate(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.text)
        report = response.json()
        fetched = self.client.get(f"/api/reports/{report['id']}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json(), report)
        exported = self.client.get(f"/api/reports/{report['id']}/markdown")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.text, report["markdown"])
        self.assertIn("attachment; filename=", exported.headers["content-disposition"])
        self.assertTrue(exported.headers["content-type"].startswith("text/markdown"))
        evaluated = self.client.post("/api/evaluate", json={"report_id": report["id"]})
        self.assertEqual(evaluated.status_code, 200)
        self.assertEqual(evaluated.json()["finding_coverage"], 1)
        self.assertIsNone(evaluated.json()["unsupported_claim_rate"])

    def test_duplicate_and_unknown_ids_rejected_without_persistence(self):
        invalid_cases = []
        for field in ("findings", "evidence"):
            case = sample_case()
            case[field].append(deepcopy(case[field][0]))
            invalid_cases.append(case)
        missing = sample_case()
        missing["findings"][0]["evidence_ids"] = ["not-available"]
        invalid_cases.append(missing)
        before = self.report_count()
        for case in invalid_cases:
            with self.subTest(case=case):
                response = self.create(case=case)
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.report_count(), before)

    def test_unknown_fields_and_malformed_json_rejected(self):
        response = self.create(unexpected="should not be silently ignored")
        self.assertEqual(response.status_code, 422)
        response = self.client.post("/api/reports", content="{broken-json", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)

    def test_oversized_body_is_rejected_before_generation(self):
        before = self.report_count()
        response = self.client.post("/api/reports", content=b"x" * 1_000_001)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.report_count(), before)

    def test_missing_evidence_remains_review_required_through_api(self):
        case = sample_case()
        case["findings"][0]["evidence_ids"] = []
        case["evidence"] = []
        response = self.create(case=case)
        self.assertEqual(response.status_code, 201, response.text)
        finding = response.json()["findings"][0]
        self.assertEqual(finding["status"], "needs_review")
        self.assertEqual(finding["claims"], [])

    def test_unconfigured_llm_returns_503_without_saving(self):
        before = self.report_count()
        with patch.dict(os.environ, {"AI_API_KEY": "", "AI_MODEL": ""}):
            response = self.create(provider="llm")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.report_count(), before)

    def test_invalid_model_citation_returns_502_without_saving(self):
        context = make_context(ReportRequest(case=sample_case()), self.main.kb)
        output = template_generate(context).model_dump()
        output["findings"][0]["claims"][0]["evidence_ids"] = ["made-up-evidence"]
        parsed = GeneratedOutput.model_validate(output)
        before = self.report_count()
        with patch.dict(os.environ, {"AI_API_KEY": "test-secret", "AI_MODEL": "test-model"}), patch("app.engine.call_llm", return_value=parsed):
            response = self.create(provider="llm")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.report_count(), before)

    def test_evidence_secrets_are_redacted_in_persisted_report(self):
        case = sample_case()
        case["evidence"][0]["content"] = "password=not-for-storage; app_user | true"
        response = self.create(case=case)
        self.assertEqual(response.status_code, 201)
        report = response.json()
        self.assertNotIn("not-for-storage", response.text)
        with sqlite3.connect(self.main.DB_PATH) as connection:
            stored = connection.execute("SELECT payload FROM reports WHERE id=?", (report["id"],)).fetchone()[0]
        self.assertNotIn("not-for-storage", stored)
        self.assertIn("REDACTED", stored)

    def test_missing_and_sql_like_report_ids_return_404(self):
        for report_id in ("does-not-exist", "x' OR '1'='1"):
            with self.subTest(report_id=report_id):
                self.assertEqual(self.client.get(f"/api/reports/{report_id}").status_code, 404)
                response = self.client.post("/api/evaluate", json={"report_id": report_id})
                self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/api/cases/does-not-exist").status_code, 404)

    def test_generation_concurrency_limit_is_exposed_as_429(self):
        with patch.object(self.main, "generation_lock") as gate:
            gate.acquire.return_value = False
            response = self.create()
            self.assertEqual(response.status_code, 429)
            gate.release.assert_not_called()

    def test_security_headers_are_present(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("script-src 'self'", response.headers["content-security-policy"])


if __name__ == "__main__":
    unittest.main()
