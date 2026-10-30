import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx

from app.engine import GenerationError
from app.models import GeneratedOutput
from app.settings import Settings


SPEC = importlib.util.spec_from_file_location(
    "gemini_diagnose_command_under_test", Path(__file__).resolve().parents[1] / "scripts" / "diagnose_gemini.py"
)
diagnose = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnose)


class DiagnoseCommandTests(unittest.TestCase):
    def settings(self, key="diagnostic-fake-key"):
        return Settings(backend="gemini", model="gemini-3.5-flash-lite", api_key=key,
                        base_url="https://generativelanguage.googleapis.com/v1beta", credential_source="environment")

    def valid_output(self):
        output = GeneratedOutput.model_validate({"findings": [{"id": "DIAG-001", "analysis": "No evidence available; review required.",
                                                              "claims": [], "remediation": []}]})
        output._generation_metadata = {"schema_profile": "minimal-v1", "model_resolved": "gemini-3.5-flash-lite",
                                       "usage": {"input_tokens": 31, "output_tokens": 18}}
        return output

    def run_with(self, metadata_response, *, output=None, failure=None):
        stdout = io.StringIO()
        with patch.object(diagnose, "get_settings", return_value=self.settings()), \
             patch.object(diagnose.httpx, "Client") as client, \
             patch.object(diagnose, "call_llm") as call, contextlib.redirect_stdout(stdout):
            client.return_value.__enter__.return_value.get.return_value = metadata_response
            if failure:
                call.side_effect = failure
            else:
                call.return_value = output or self.valid_output()
            code = diagnose.run()
        return code, stdout.getvalue(), client, call

    def test_success_uses_metadata_header_and_one_synthetic_request(self):
        code, text, client, call = self.run_with(httpx.Response(200, json={"supportedGenerationMethods": ["generateContent"]}))
        self.assertEqual(code, 0)
        get = client.return_value.__enter__.return_value.get
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite")
        self.assertEqual(get.call_args.kwargs["headers"]["x-goog-api-key"], "diagnostic-fake-key")
        call.assert_called_once()
        context = call.call_args.args[0]
        self.assertEqual(context["title"], "Synthetic connectivity check")
        self.assertTrue(context["grounding"])
        self.assertFalse(context["rag"])
        self.assertEqual(len(context["findings"]), 1)
        self.assertEqual(context["findings"][0]["evidence"], [])
        self.assertEqual(context["findings"][0]["owasp"], [])
        self.assertIn("PASS", text)
        self.assertIn("may consume API quota", text)
        self.assertIn("gemini-3.5-flash-lite", text)
        self.assertNotIn("diagnostic-fake-key", text)

    def test_missing_key_prevents_all_network_calls(self):
        stdout = io.StringIO()
        with patch.object(diagnose, "get_settings", return_value=self.settings(key="")), \
             patch.object(diagnose.httpx, "Client") as client, patch.object(diagnose, "call_llm") as call, \
             contextlib.redirect_stdout(stdout):
            code = diagnose.run()
        self.assertEqual(code, 1)
        client.assert_not_called()
        call.assert_not_called()
        self.assertIn("not configured", stdout.getvalue())

    def test_metadata_400_reports_only_safe_hint_without_calling_model(self):
        raw_secret = "private-metadata-secret"
        response = httpx.Response(400, json={"error": {"message": f"Invalid responseJsonSchema; api_key={raw_secret}",
            "details": [{"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [
                {"field": "generation_config.response_json_schema", "description": raw_secret}]}]}})
        code, text, _, call = self.run_with(response)
        self.assertEqual(code, 1)
        call.assert_not_called()
        self.assertIn("provider_http_400", text)
        self.assertIn("invalid_schema", text)
        self.assertNotIn(raw_secret, text)
        self.assertNotIn("diagnostic-fake-key", text)

    def test_structured_check_400_is_safely_displayed(self):
        safe_hint = {"kind": "invalid_schema", "message": "Schema chưa tương thích.", "fields": ["generationConfig.responseJsonSchema"]}
        failure = GenerationError("Gemini HTTP 400: schema rejected", code="provider_http_400", provider_status=400, diagnostic=safe_hint)
        code, text, _, call = self.run_with(httpx.Response(200, json={}), failure=failure)
        self.assertEqual(code, 1)
        call.assert_called_once()
        self.assertIn("provider_http_400", text)
        self.assertIn("generationConfig.responseJsonSchema", text)
        self.assertNotIn("diagnostic-fake-key", text)

    def test_malformed_metadata_does_not_call_model_or_print_response(self):
        for response in (httpx.Response(200, json=["private-response"]), httpx.Response(200, text="private-response-invalid-json")):
            with self.subTest(content_type=response.headers.get("content-type")):
                code, text, _, call = self.run_with(response)
                self.assertEqual(code, 1)
                call.assert_not_called()
                self.assertIn("Raw response withheld", text)
                self.assertNotIn("private-response", text)

    def test_absent_optional_generation_metadata_is_explicitly_missing(self):
        output = self.valid_output()
        output._generation_metadata = {}
        code, text, _, _ = self.run_with(httpx.Response(200, json={}), output=output)
        self.assertEqual(code, 0)
        self.assertIn("Returned model version: not supplied", text)
        self.assertIn("Token usage: {}", text)

    def test_network_error_does_not_print_url_or_credentials(self):
        stdout = io.StringIO()
        with patch.object(diagnose, "get_settings", return_value=self.settings()), \
             patch.object(diagnose.httpx, "Client") as client, patch.object(diagnose, "call_llm") as call, \
             contextlib.redirect_stdout(stdout):
            client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError("https://private.invalid/?key=diagnostic-fake-key")
            code = diagnose.run()
        self.assertEqual(code, 1)
        call.assert_not_called()
        self.assertNotIn("private.invalid", stdout.getvalue())
        self.assertNotIn("diagnostic-fake-key", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
