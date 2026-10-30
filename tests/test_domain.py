import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from app.knowledge import CORPUS, KnowledgeBase
from app.models import Case
from app.privacy import redact, redact_value


def sample_case():
    return {
        "title": "PostgreSQL permission review",
        "database": "PostgreSQL",
        "findings": [{
            "id": "F001", "title": "Application role is a superuser",
            "category": "excessive_privileges", "severity": "high",
            "description": "The application role has broad administrative privileges.",
            "asset": "lab-postgres/application", "evidence_ids": ["E001"],
        }],
        "evidence": [{
            "id": "E001", "source": "authorized lab query",
            "content": "SELECT rolname, rolsuper FROM pg_roles; app_user | true",
            "collected_at": "2026-10-30T00:00:00Z",
        }],
    }


class InputValidationTests(unittest.TestCase):
    def test_valid_case_preserves_evidence_reference(self):
        case = Case.model_validate(sample_case())
        self.assertEqual(case.findings[0].evidence_ids, ["E001"])

    def test_duplicate_finding_and_evidence_ids_are_rejected(self):
        for field in ("findings", "evidence"):
            with self.subTest(field=field):
                case = sample_case()
                case[field].append(deepcopy(case[field][0]))
                with self.assertRaises(ValidationError):
                    Case.model_validate(case)

    def test_unknown_evidence_reference_is_rejected(self):
        case = sample_case()
        case["findings"][0]["evidence_ids"] = ["E-DOES-NOT-EXIST"]
        with self.assertRaises(ValidationError):
            Case.model_validate(case)

    def test_duplicate_evidence_reference_is_rejected(self):
        case = sample_case()
        case["findings"][0]["evidence_ids"] *= 2
        with self.assertRaises(ValidationError):
            Case.model_validate(case)

    def test_absent_evidence_is_valid_for_abstention(self):
        case = sample_case()
        case["findings"][0]["evidence_ids"] = []
        case["evidence"] = []
        self.assertEqual(Case.model_validate(case).evidence, [])

    def test_total_evidence_budget_is_enforced(self):
        case = sample_case()
        case["evidence"] = [
            {"id": f"E{index}", "source": "lab", "content": "x" * 12000}
            for index in range(9)
        ]
        case["findings"][0]["evidence_ids"] = ["E0"]
        with self.assertRaises(ValidationError):
            Case.model_validate(case)


class KnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()

    def test_official_sources_have_pinned_provenance(self):
        self.assertEqual(len(self.kb.sources), 4)
        self.assertGreater(len(self.kb.chunks), 4)
        for source in self.kb.sources:
            self.assertEqual(len(source["revision"]), 40)
            self.assertTrue(source["snapshot_url"].startswith("https://raw.githubusercontent.com/OWASP/"))
            self.assertEqual(len(source["sha256"]), 64)

    def test_retrieval_returns_relevant_attributable_chunks(self):
        chunks = self.kb.search("sql_injection", "prepared statements parameterized SQL queries")
        self.assertTrue(chunks)
        self.assertTrue(any(chunk["source_id"] == "sql-injection" for chunk in chunks))
        for chunk in chunks:
            self.assertIn("id", chunk)
            self.assertIn("section", chunk)
            self.assertGreater(chunk["score"], 0)
            self.assertLessEqual(len(chunk["text"]), 1800)

    def test_retrieval_order_is_repeatable(self):
        first = self.kb.search("excessive_privileges", "least privilege database roles")
        self.assertEqual(first, self.kb.search("excessive_privileges", "least privilege database roles"))

    def test_modified_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(CORPUS, root, dirs_exist_ok=True)
            manifest = json.loads((root / "manifest.json").read_text())
            changed = root / manifest["sources"][0]["file"]
            changed.write_text(changed.read_text() + "\nUnexpected altered content\n")
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                KnowledgeBase(root)


class RedactionTests(unittest.TestCase):
    def test_credentials_are_redacted_in_common_formats(self):
        examples = [
            ("password=actual-secret", "actual-secret"),
            ('password="a secret with spaces"', "a secret with spaces"),
            ("postgresql://lab:db-secret@localhost/db", "db-secret"),
            ("mysql://lab:db-secret@localhost/db", "db-secret"),
            ("Authorization: Bearer bearer-secret", "bearer-secret"),
            ("sk-abcdefghijklmnopqrstuvwx", "sk-abcdefghijklmnopqrstuvwx"),
        ]
        for raw, secret in examples:
            with self.subTest(raw=raw):
                cleaned = redact(raw)
                self.assertNotIn(secret, cleaned)
                self.assertIn("REDACTED", cleaned)

    def test_nested_redaction_preserves_non_secret_structure(self):
        value = {"items": [{"text": "password=secret-value", "count": 3}], "active": True}
        cleaned = redact_value(value)
        self.assertNotIn("secret-value", json.dumps(cleaned))
        self.assertEqual(cleaned["items"][0]["count"], 3)
        self.assertTrue(cleaned["active"])
        self.assertIn("secret-value", value["items"][0]["text"])

    def test_non_sensitive_evidence_is_unchanged(self):
        text = "SELECT rolname, rolsuper FROM pg_roles; app_user | true"
        self.assertEqual(redact(text), text)


if __name__ == "__main__":
    unittest.main()
