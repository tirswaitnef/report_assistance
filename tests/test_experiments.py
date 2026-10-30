import csv
import importlib
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.engine import GenerationError, generate_report
from app.experiments import ExperimentBusy, ExperimentManager, ExperimentRequest
from app.knowledge import KnowledgeBase
from app.research import REVIEW_FIELDS
from tests.test_domain import sample_case


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()

    def setUp(self):
        self.storage = tempfile.TemporaryDirectory(prefix="db-experiment-test-")
        self.addCleanup(self.storage.cleanup)
        self.directory = Path(self.storage.name)
        self.manager = ExperimentManager(self.directory, self.kb)

    def request(self, **changes):
        payload = {"case": sample_case(), "provider": "template", "repeats": 1}
        payload.update(changes)
        return ExperimentRequest.model_validate(payload)

    def test_four_conditions_have_fixed_repetitions_and_blank_human_scores(self):
        state = self.manager.start(self.request(repeats=3), background=False)
        self.assertEqual(state["status"], "completed")
        self.assertEqual((state["total"], state["completed"], state["succeeded"], state["failed"]), (12, 12, 12, 0))
        self.assertIsNone(state["current"])
        self.assertTrue(state["download_ready"])
        for repeat in (1, 2, 3):
            rows = [r for r in state["runs"] if r["repeat"] == repeat]
            self.assertEqual({r["condition"] for r in rows}, {"G0R0", "G0R1", "G1R0", "G1R1"})
        folder = self.manager.folder(state["id"])
        reports = [json.loads(p.read_text(encoding="utf-8")) for p in (folder / "reports").glob("*.json")]
        self.assertEqual(len(reports), 12)
        self.assertEqual(len(list((folder / "reports").glob("*.md"))), 12)
        for report in reports:
            for finding in report["findings"]:
                if not report["mode"]["grounding"]:
                    self.assertEqual(finding["evidence"], [])
                    self.assertEqual(finding["evidence_ids"], [])
                if not report["mode"]["rag"]:
                    self.assertEqual(finding["owasp"], [])
        with (folder / "expert-review.csv").open(encoding="utf-8-sig", newline="") as handle:
            review = list(csv.DictReader(handle))
        self.assertTrue(review)
        annotation = set(REVIEW_FIELDS) - {"blind_id", "finding_id", "row_type", "remediation_index"}
        for row in review:
            self.assertTrue(all(row[field] == "" for field in annotation))

    def test_manifest_preserves_study_and_case_provenance(self):
        study = {"case_id": "case-001", "cluster_id": "cluster-001", "split": "test", "engine_version": "PostgreSQL 16"}
        state = self.manager.start(self.request(study=study), background=False)
        folder = self.manager.folder(state["id"])
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["study"], study)
        self.assertEqual(len(manifest["case_sha256"]), 64)
        self.assertEqual(len(manifest["prompt_sha256"]), 64)
        self.assertEqual(len(manifest["owasp_sources"]), 4)
        self.assertEqual(manifest["raw_rejected_output"], "not_retained; safe failure codes only")
        report = json.loads(next((folder / "reports").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(report["experiment"]["cluster_id"], study["cluster_id"])

    def test_seed_preserves_condition_order_without_reusing_blind_ids(self):
        request = self.request(repeats=2, seed=731)
        first = self.manager.start(request, background=False)
        second = self.manager.start(request, background=False)
        fields = lambda state: [(r["repeat"], r["condition"]) for r in state["runs"]]
        self.assertEqual(fields(first), fields(second))
        self.assertTrue({r["blind_id"] for r in first["runs"]}.isdisjoint({r["blind_id"] for r in second["runs"]}))

    def test_provider_failure_remains_in_attempt_denominator_and_archive(self):
        calls = []

        def generator(request, kb):
            calls.append(request)
            if len(calls) == 1:
                raise GenerationError("Quota unavailable", code="provider_http_429", provider_status=429)
            return generate_report(request, kb)

        manager = ExperimentManager(self.directory, self.kb, generator=generator)
        state = manager.start(self.request(), background=False)
        self.assertEqual(len(calls), 4)
        self.assertEqual((state["status"], state["completed"], state["failed"], state["succeeded"]), ("completed_with_errors", 4, 1, 3))
        failed = [r for r in state["runs"] if r["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["provider_status"], 429)
        self.assertEqual(failed[0]["error_code"], "provider_http_429")
        with ZipFile(manager.archive(state["id"])) as archive:
            rows = [json.loads(line) for line in archive.read(f"{state['id']}/runs.jsonl").decode().splitlines()]
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(r["status"] == "failed" for r in rows), 1)

    def test_arbitrary_exception_text_is_not_persisted(self):
        generator = Mock(side_effect=RuntimeError("sensitive-provider-token-do-not-log"))
        manager = ExperimentManager(self.directory, self.kb, generator=generator)
        state = manager.start(self.request(), background=False)
        self.assertEqual(state["failed"], 4)
        self.assertNotIn("sensitive-provider-token-do-not-log", json.dumps(state))
        for path in manager.folder(state["id"]).rglob("*.json*"):
            self.assertNotIn("sensitive-provider-token-do-not-log", path.read_text(encoding="utf-8"))

    def test_archive_contains_redacted_case_not_local_credentials(self):
        (self.directory / "settings.json").write_text('{"GEMINI_API_KEY":"never-share-this-key"}')
        case = sample_case()
        case["evidence"][0]["content"] = "password=private-evidence-secret; role_superuser=true"
        state = self.manager.start(self.request(case=case), background=False)
        with ZipFile(self.manager.archive(state["id"])) as archive:
            self.assertIsNone(archive.testzip())
            names = archive.namelist()
            self.assertTrue(any(name.endswith("/expert-review.csv") for name in names))
            self.assertFalse(any(name.endswith("settings.json") or ".." in name for name in names))
            content = b"\n".join(archive.read(name) for name in names)
            self.assertNotIn(b"never-share-this-key", content)
            self.assertNotIn(b"private-evidence-secret", content)

    def test_unconfigured_llm_does_not_call_generator_or_create_experiment(self):
        generator = Mock()
        manager = ExperimentManager(self.directory, self.kb, generator=generator)
        with patch("app.experiments.public_settings", return_value={"backend": "gemini", "model": "example-model", "configured": False, "credential_source": "missing"}):
            with self.assertRaises(GenerationError):
                manager.start(self.request(provider="llm"), background=False)
        generator.assert_not_called()
        self.assertIsNone(manager.active_id)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_active_job_blocks_duplicate_start_and_download_until_finished(self):
        entered, release = threading.Event(), threading.Event()

        def generator(request, kb):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test release timeout")
            return generate_report(request, kb)

        manager = ExperimentManager(self.directory, self.kb, generator=generator)
        state = manager.start(self.request())
        try:
            self.assertTrue(entered.wait(3))
            with self.assertRaises(ExperimentBusy):
                manager.start(self.request())
            with self.assertRaises(ExperimentBusy):
                manager.archive(state["id"])
        finally:
            release.set()
        deadline = time.monotonic() + 5
        while manager.active_id and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIsNone(manager.active_id)
        self.assertEqual(manager.status(state["id"])["status"], "completed")

    def test_restart_marks_pending_runs_interrupted_without_calling_generator(self):
        with patch("app.experiments.threading.Thread"):
            state = self.manager.start(self.request())
        generator = Mock()
        restarted = ExperimentManager(self.directory, self.kb, generator=generator)
        recovered = restarted.status(state["id"])
        self.assertEqual(recovered["status"], "failed")
        self.assertEqual(recovered["completed"], 0)
        self.assertTrue(recovered["download_ready"])
        self.assertTrue(all(r["status"] == "not_attempted_or_interrupted" for r in recovered["runs"]))
        generator.assert_not_called()

    def test_invalid_ids_and_study_metadata_are_rejected(self):
        for value in ("../settings", "missing", "f" * 32, "A" * 32):
            with self.subTest(value=value), self.assertRaises(FileNotFoundError):
                self.manager.status(value)
        for changes in ({"repeats": 0}, {"repeats": 6}, {"study": {"case_id": "../escape"}}, {"study": {"split": "invented"}}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.request(**changes)

    def test_setup_failure_releases_active_slot(self):
        with patch("app.experiments.save_json", side_effect=PermissionError("cannot write")):
            with self.assertRaises(PermissionError):
                self.manager.start(self.request(), background=False)
        self.assertIsNone(self.manager.active_id)


class ExperimentAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = importlib.import_module("app.main")

    def setUp(self):
        self.storage = tempfile.TemporaryDirectory(prefix="db-experiment-api-")
        self.addCleanup(self.storage.cleanup)
        manager = ExperimentManager(Path(self.storage.name), self.main.kb)
        self.override = patch.object(self.main, "experiments", manager)
        self.override.start()
        self.addCleanup(self.override.stop)
        self.client = TestClient(self.main.app)
        self.addCleanup(self.client.close)

    def test_api_creates_polls_and_downloads_completed_archive(self):
        response = self.client.post("/api/experiments", json={"case": sample_case(), "provider": "template", "repeats": 1})
        self.assertEqual(response.status_code, 202, response.text)
        experiment_id = response.json()["id"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = self.client.get(f"/api/experiments/{experiment_id}")
            self.assertEqual(status.status_code, 200)
            if status.json()["download_ready"]:
                break
            time.sleep(0.01)
        self.assertEqual(status.json()["status"], "completed")
        self.assertEqual(status.json()["completed"], 4)
        download = self.client.get(f"/api/experiments/{experiment_id}/download")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers["content-type"], "application/zip")
        with ZipFile(io.BytesIO(download.content)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn(f"{experiment_id}/manifest.json", archive.namelist())

    def test_api_invalid_repeats_unknown_id_and_missing_llm(self):
        response = self.client.post("/api/experiments", json={"case": sample_case(), "provider": "template", "repeats": 6})
        self.assertEqual(response.status_code, 422)
        for suffix in ("", "/download"):
            self.assertEqual(self.client.get("/api/experiments/" + "f" * 32 + suffix).status_code, 404)
        with patch("app.experiments.public_settings", return_value={"backend": "gemini", "model": "example-model", "configured": False, "credential_source": "missing"}):
            response = self.client.post("/api/experiments", json={"case": sample_case(), "provider": "llm"})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
