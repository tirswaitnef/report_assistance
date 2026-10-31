import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("research_lab_collector_tests", Path(__file__).resolve().parents[1] / "lab" / "collect.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def pg_observation(control=False):
    return {"server_version": "16.13 (test build)",
            "role": {"rolname": "lab_app", "rolsuper": not control, "rolcreaterole": False, "rolcreatedb": False},
            "ssl": "on" if control else "off",
            "hba": ([{"type": "hostssl", "address": "0.0.0.0", "auth_method": "scram-sha-256", "error": None},
                     {"type": "hostnossl", "address": "0.0.0.0", "auth_method": "reject", "error": None}]
                    if control else [{"type": "host", "address": "0.0.0.0", "auth_method": "trust", "error": None}]),
            "log_connections": "on" if control else "off", "log_disconnections": "on" if control else "off", "fixture_rows": 3}


def mysql_settings(control=False):
    return {"server_version": "8.4.8", "require_secure_transport": int(control), "fixture_rows": 3}


class FakeDocker:
    def __init__(self, fail_service=None, incorrect_service=None):
        self.calls = []
        self.fail_service = fail_service
        self.incorrect_service = incorrect_service

    def __call__(self, command):
        self.calls.append(command)
        if command[:2] == ["docker", "compose"]:
            if "exec" in command:
                service = command[command.index("-T") + 1]
                if service == self.fail_service:
                    raise collector.CollectionError("Read-only observation failed")
                control = service.endswith("-b")
                if service == self.incorrect_service:
                    control = not control
                if service.startswith("pg-"):
                    return json.dumps(pg_observation(control))
                if command[-1] == collector.MYSQL_SETTINGS_QUERY:
                    return json.dumps(mysql_settings(control))
                return ("GRANT USAGE ON *.* TO `lab_app`@`%`\nGRANT SELECT ON `labdb`.* TO `lab_app`@`%`" if control
                        else "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP ON *.* TO `lab_app`@`%`")
            if "ps" in command:
                return "a" * 64
        if command[:2] == ["docker", "inspect"]:
            return "sha256:" + "b" * 64 if command[3] == "{{.Image}}" else "test-image@sha256:" + "b" * 64
        if command[:3] == ["docker", "image", "inspect"]:
            return json.dumps(["test-image@sha256:" + "b" * 64])
        raise AssertionError(f"Unexpected command shape: {command[:4]}")


class LabObservationTests(unittest.TestCase):
    def test_postgres_requires_measured_role_rules_and_populated_fixture(self):
        for key, invalid in (("role", None), ("hba", []), ("ssl", "unknown"), ("fixture_rows", 0)):
            sample = pg_observation()
            sample[key] = invalid
            with self.subTest(field=key), self.assertRaises(collector.CollectionError):
                collector.parse_postgres(json.dumps(sample))
        error = pg_observation()
        error["hba"][0]["error"] = "parse error"
        with self.assertRaises(collector.CollectionError):
            collector.parse_postgres(json.dumps(error))

    def test_mysql_expanded_global_privileges_and_schema_controls_are_distinct(self):
        self.assertTrue(collector.mysql_has_global_privileges(["GRANT SELECT, INSERT, DROP ON *.* TO `lab_app`@`%`"]))
        self.assertTrue(collector.mysql_has_global_privileges(["GRANT ALL PRIVILEGES ON *.* TO 'lab_app'@'%'"]))
        self.assertFalse(collector.mysql_has_global_privileges(["GRANT USAGE ON *.* TO `lab_app`@`%`", "GRANT SELECT ON `labdb`.* TO `lab_app`@`%`"]))
        with self.assertRaises(collector.CollectionError):
            collector.parse_mysql(json.dumps(mysql_settings()), "not grant output")

    def test_operational_state_checks_use_observed_flags_not_service_name_alone(self):
        self.assertTrue(collector.check_expected_state("pg-b", "PostgreSQL", pg_observation(True))["passed"])
        self.assertFalse(collector.check_expected_state("pg-b", "PostgreSQL", pg_observation(False))["passed"])

    def test_command_failure_never_echoes_process_stderr(self):
        with patch.object(collector.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["docker"], stderr="private-password-value")):
            with self.assertRaises(collector.CollectionError) as error:
                collector.run_command(["docker", "compose", "ps"])
        self.assertNotIn("private-password-value", str(error.exception))


class LabCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="db-report-lab-test-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "collection"

    def test_four_measured_cases_validate_without_state_label_leakage(self):
        docker = FakeDocker()
        manifest = collector.Collector(runner=docker).collect(self.output)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["case_count"], 4)
        cases = sorted((self.output / "cases").glob("*.json"))
        self.assertEqual(len(cases), 4)
        for path in cases:
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(collector.validate_case(value))
            source = path.read_text(encoding="utf-8")
            for hidden in ("pg-a", "pg-b", "mysql-a", "mysql-b", "hardened_control", "deliberately_weak"):
                self.assertNotIn(hidden, source)
            self.assertTrue(all(e["collected_at"] for e in value["evidence"]))
            self.assertTrue(all("Do not treat" in finding["description"] and "confirmed vulnerability" in finding["description"] for finding in value["findings"]))
        reference = json.loads((self.output / "reference-candidates.json").read_text(encoding="utf-8"))
        self.assertTrue(reference["requires_expert_adjudication"])
        self.assertFalse(reference["is_final_gold_standard"])
        self.assertEqual({case["lab_condition"] for case in reference["cases"]}, {"deliberately_weak", "hardened_control"})
        self.assertEqual(len({case["cluster_id"] for case in manifest["cases"]}), 2)
        for case in manifest["cases"]:
            for source, digest in case["raw_observation_sha256"].items():
                path = self.output / "raw" / f"{case['case_id']}-{source}.txt"
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertTrue(all("Env" not in " ".join(command) for command in docker.calls))
        self.assertFalse(any(".local/lab.env" in path.name for path in self.output.rglob("*")))

    def test_sql_commands_are_read_only_and_password_is_an_internal_variable(self):
        docker = FakeDocker()
        collector.Collector(runner=docker).collect(self.output)
        sql = [command for command in docker.calls if "exec" in command]
        self.assertEqual(len(sql), 6)
        self.assertTrue(all(command[-1].lstrip().upper().startswith(("SELECT", "SHOW")) for command in sql))
        mysql = [command for command in sql if "mysql-a" in command or "mysql-b" in command]
        self.assertTrue(all(collector.MYSQL_SHELL in command for command in mysql))
        self.assertTrue(all("--skip-column-names" in command[command.index("-c") + 1] for command in mysql))

    def test_recapturing_same_scenarios_does_not_invent_independent_clusters(self):
        first = collector.Collector(runner=FakeDocker()).collect(self.output)
        second = collector.Collector(runner=FakeDocker()).collect(self.output.with_name("second-capture"), seed=7)
        self.assertNotEqual(first["run_id"], second["run_id"])
        expected = {"DBLAB-v1-PG-CONFIG", "DBLAB-v1-MY-CONFIG"}
        self.assertEqual({case["cluster_id"] for case in first["cases"]}, expected)
        self.assertEqual({case["cluster_id"] for case in second["cases"]}, expected)

    def test_failed_query_never_exports_fabricated_or_partial_case_dataset(self):
        with self.assertRaises(collector.CollectionError):
            collector.Collector(runner=FakeDocker(fail_service="mysql-a")).collect(self.output)
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["observed_service_count"], 2)
        self.assertFalse((self.output / "cases").exists())

    def test_incorrect_control_configuration_exports_failed_checks_not_cases(self):
        with self.assertRaises(collector.CollectionError):
            collector.Collector(runner=FakeDocker(incorrect_service="pg-b")).collect(self.output)
        checks = json.loads((self.output / "health" / "statechecks.json").read_text(encoding="utf-8"))
        self.assertFalse(checks["passed"])
        self.assertFalse((self.output / "cases").exists())

    def test_existing_collection_is_preserved(self):
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("preserve")
        with self.assertRaises(FileExistsError):
            collector.Collector(runner=FakeDocker()).collect(self.output)
        self.assertEqual(marker.read_text(), "preserve")

    def test_only_managed_project_and_services_are_accepted(self):
        with self.assertRaises(collector.CollectionError):
            collector.Collector(project="unrelated-production")
        with self.assertRaises(collector.CollectionError):
            collector.Collector(runner=FakeDocker()).observe_service("external-host")


if __name__ == "__main__":
    unittest.main()
