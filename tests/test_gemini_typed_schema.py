import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import importlib.util
from unittest.mock import patch

from pydantic import ValidationError

from app.gemini_schema import (
    SCHEMA_PROFILE, TYPED_SCHEMA_PROFILE, gemini_format,
    gemini_schema_profile, gemini_typed_response_schema,
)
from app.models import GeneratedOutput
from app.settings import get_settings, public_settings


class TypedSchemaTests(unittest.TestCase):
    def test_typed_schema_is_inline_native_structure_for_nested_report_fields(self):
        schema = gemini_typed_response_schema()
        self.assertEqual(schema["type"], "OBJECT")
        self.assertEqual(schema["required"], ["findings"])
        finding = schema["properties"]["findings"]["items"]
        self.assertEqual(finding["type"], "OBJECT")
        self.assertEqual(set(finding["properties"]), {"id", "analysis", "claims", "remediation"})
        claim = finding["properties"]["claims"]["items"]
        self.assertEqual(set(claim["properties"]), {"text", "evidence_ids"})
        self.assertEqual(claim["properties"]["evidence_ids"]["items"], {"type": "STRING"})
        remediation = finding["properties"]["remediation"]["items"]
        self.assertEqual(set(remediation["properties"]), {"action", "rationale", "verification", "owasp_refs"})

        def check(node):
            self.assertTrue(set(node) <= {"type", "properties", "required", "items"})
            self.assertIn(node["type"], {"OBJECT", "ARRAY", "STRING"})
            for child in node.get("properties", {}).values():
                check(child)
            if "items" in node:
                check(node["items"])
        check(schema)

    def test_wire_alternatives_are_explicit_and_never_combined(self):
        typed = gemini_format("typed")
        json_schema = gemini_format("json_schema")
        self.assertEqual(typed["responseMimeType"], "application/json")
        self.assertIn("responseSchema", typed)
        self.assertNotIn("responseJsonSchema", typed)
        self.assertIn("responseJsonSchema", json_schema)
        self.assertNotIn("responseSchema", json_schema)
        self.assertEqual(gemini_schema_profile("typed"), TYPED_SCHEMA_PROFILE)
        self.assertEqual(gemini_schema_profile("json_schema"), SCHEMA_PROFILE)
        for function in (gemini_format, gemini_schema_profile):
            with self.assertRaises(ValueError):
                function("auto")

    def test_full_response_validation_survives_minimal_generation_hints(self):
        original = copy.deepcopy(GeneratedOutput.model_json_schema())
        gemini_typed_response_schema()
        self.assertEqual(GeneratedOutput.model_json_schema(), original)
        for data in (
            {"findings": []},
            {"findings": [{"id": "F1", "analysis": "x" * 6001}]},
            {"findings": [{"id": "F1", "analysis": "ok", "unknown": True}]},
        ):
            with self.subTest(data_has_findings=bool(data["findings"])), self.assertRaises(ValidationError):
                GeneratedOutput.model_validate(data)

    def test_recursive_or_nonlocal_schema_references_fail_closed(self):
        recursive = {"type": "object", "properties": {"root": {"$ref": "#/$defs/Loop"}},
                     "$defs": {"Loop": {"type": "object", "properties": {"again": {"$ref": "#/$defs/Loop"}}}}}
        external = {"type": "object", "properties": {"root": {"$ref": "https://example.invalid/schema"}}}
        for value in (recursive, external):
            with patch.object(GeneratedOutput, "model_json_schema", return_value=value), self.assertRaises(ValueError):
                gemini_typed_response_schema()

    def test_default_wire_schema_matches_the_user_accepted_typed_probe(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "probe_gemini.py"
        spec = importlib.util.spec_from_file_location("typed_schema_probe_comparison", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        probes = {item["name"]: item["body"] for item in module.build_probes()}
        self.assertEqual(gemini_format("typed"), probes["typed_report_schema"]["generationConfig"])
        self.assertEqual(probes["application_request"]["generationConfig"]["responseSchema"], gemini_typed_response_schema())
        self.assertNotIn("responseJsonSchema", probes["application_request"]["generationConfig"])


class SchemaModeSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "settings.json"
        environment = patch.dict(os.environ, {"GEMINI_API_KEY": "fake-mode-test-key"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        local_path = patch("app.settings.LOCAL_SETTINGS", self.path)
        local_path.start()
        self.addCleanup(local_path.stop)

    def test_typed_is_default_and_public_configuration_exposes_only_mode(self):
        self.assertTrue(get_settings().configured)
        self.assertEqual(get_settings().schema_mode, "typed")
        self.assertEqual(public_settings()["schema_mode"], "typed")
        self.assertNotIn("fake-mode-test-key", json.dumps(public_settings()))

    def test_local_mode_and_environment_override_are_respected(self):
        self.path.write_text(json.dumps({"GEMINI_SCHEMA_MODE": "json_schema"}), encoding="utf-8")
        self.assertEqual(get_settings().schema_mode, "json_schema")
        with patch.dict(os.environ, {"GEMINI_SCHEMA_MODE": "typed"}):
            self.assertEqual(get_settings().schema_mode, "typed")
            self.assertTrue(get_settings().configured)
        with patch.dict(os.environ, {"GEMINI_SCHEMA_MODE": ""}):
            self.assertFalse(get_settings().configured)

    def test_unsupported_mode_fails_closed_without_reflecting_value(self):
        with patch.dict(os.environ, {"GEMINI_SCHEMA_MODE": "private-invalid-mode"}):
            settings = get_settings()
            self.assertFalse(settings.configured)
            self.assertNotIn("private-invalid-mode", settings.error)
            self.assertIsNone(public_settings()["schema_mode"])
            self.assertNotIn("private-invalid-mode", json.dumps(public_settings()))

    def test_openai_ignores_gemini_schema_mode(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "AI_API_KEY": "fake-legacy-key",
                                     "AI_MODEL": "legacy-model", "GEMINI_SCHEMA_MODE": "unsupported"}):
            settings = get_settings()
            self.assertTrue(settings.configured)
            self.assertEqual(settings.backend, "openai")
            self.assertEqual(settings.schema_mode, "typed")


if __name__ == "__main__":
    unittest.main()
