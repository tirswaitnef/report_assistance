import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from app.settings import Settings


SPEC = importlib.util.spec_from_file_location(
    "gemini_probe_under_test", Path(__file__).resolve().parents[1] / "scripts" / "probe_gemini.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class GeminiProbeTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory(prefix="gemini-probe-test-")
        self.addCleanup(self.storage.cleanup)
        self.root = Path(self.storage.name)
        self.settings = Settings(backend="gemini", model="gemini-3.5-flash-lite", api_key="fake-probe-key-only",
                                 base_url="https://generativelanguage.googleapis.com/v1beta", credential_source="environment")

    def invoke(self, responses, *, only=None, settings=None):
        output = io.StringIO()
        with patch.object(probe, "ROOT", self.root), patch.object(probe, "get_settings", return_value=settings or self.settings), \
             patch.object(probe.httpx, "Client") as client, contextlib.redirect_stdout(output):
            client.return_value.__enter__.return_value.post.side_effect = responses
            code = probe.run(only=only)
        return code, output.getvalue(), client.return_value.__enter__.return_value.post

    def success(self):
        # Acceptance of request parameters is independent of report completeness.
        return httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [
            {"text": "PRIVATE-CANDIDATE-NOT-FOR-LOGS"}]}}]})

    def saved_reports(self):
        return list((self.root / ".local" / "diagnostics").glob("*.json"))

    def test_default_success_sends_eight_isolated_synthetic_probes(self):
        code, text, post = self.invoke([self.success() for _ in range(8)])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_count, 8)
        bodies = []
        for call in post.call_args_list:
            endpoint = call.args[0]
            self.assertEqual(endpoint, "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent")
            self.assertNotIn("?", endpoint)
            self.assertEqual(call.kwargs["headers"]["x-goog-api-key"], self.settings.api_key)
            bodies.append(call.kwargs["json"])
        self.assertNotIn("generationConfig", bodies[0])
        self.assertNotIn("systemInstruction", bodies[0])
        self.assertEqual(bodies[1]["generationConfig"], {"temperature": 0})
        self.assertEqual(bodies[2]["generationConfig"], {"maxOutputTokens": 8192})
        self.assertNotIn(self.settings.api_key, text)
        self.assertNotIn("PRIVATE-CANDIDATE-NOT-FOR-LOGS", text)
        self.assertTrue(self.saved_reports())
        saved = "\n".join(path.read_text(encoding="utf-8") for path in self.saved_reports())
        self.assertNotIn(self.settings.api_key, saved)
        self.assertNotIn("PRIVATE-CANDIDATE-NOT-FOR-LOGS", saved)

    def test_first_plain_failure_stops_without_schema_requests(self):
        code, text, post = self.invoke([httpx.Response(400, json={"error": {"message": "Request contains an invalid argument."}})])
        self.assertEqual(code, 1)
        self.assertEqual(post.call_count, 1)
        self.assertIn("text_minimal", text)

    def test_schema_failure_runs_inline_alternatives_and_retains_failed_attempt(self):
        responses = [self.success() for _ in range(5)] + [httpx.Response(400, json={"error": {
            "message": "Request contains an invalid argument."}})] + [self.success() for _ in range(4)]
        code, _, post = self.invoke(responses)
        self.assertEqual(code, 1)
        self.assertEqual(post.call_count, 10)
        inline = post.call_args_list[6].kwargs["json"]["generationConfig"]
        typed = post.call_args_list[7].kwargs["json"]["generationConfig"]
        self.assertNotIn("$defs", json.dumps(inline))
        self.assertNotIn("$ref", json.dumps(inline))
        self.assertEqual(typed["responseSchema"]["type"], "OBJECT")
        self.assertNotIn("responseJsonSchema", typed)
        self.assertNotIn("additionalProperties", json.dumps(typed))
        artifact = json.loads(self.saved_reports()[0].read_text(encoding="utf-8"))
        self.assertEqual(len(artifact["results"]), 10)
        self.assertEqual(artifact["results"][5]["http_status"], 400)

    def test_quota_failure_stops_without_retrying(self):
        code, _, post = self.invoke([self.success(), httpx.Response(429, json={"error": {"message": "Quota exceeded"}})])
        self.assertEqual(code, 1)
        self.assertEqual(post.call_count, 2)

    def test_bad_configuration_prevents_network_calls(self):
        settings = Settings(backend="gemini", model="gemini-3.5-flash-lite", api_key="")
        with patch.object(probe, "get_settings", return_value=settings), patch.object(probe.httpx, "Client") as client, \
             contextlib.redirect_stdout(io.StringIO()):
            code = probe.run()
        self.assertEqual(code, 2)
        client.assert_not_called()

    def test_unknown_probe_name_prevents_network_calls(self):
        code, _, post = self.invoke([], only="not-a-real-probe")
        self.assertEqual(code, 2)
        post.assert_not_called()

    def test_only_selected_probe_is_sent(self):
        code, text, post = self.invoke([self.success()], only="text_minimal")
        self.assertEqual(code, 0)
        self.assertEqual(post.call_count, 1)
        self.assertIn("text_minimal", text)

    def test_reflected_key_and_candidate_never_reach_output_or_artifact(self):
        message = f"Request contains an invalid argument. key={self.settings.api_key}"
        code, text, _ = self.invoke([httpx.Response(400, json={"error": {"message": message, "status": "INVALID_ARGUMENT"}})])
        self.assertEqual(code, 1)
        self.assertNotIn(self.settings.api_key, text)
        for path in self.saved_reports():
            self.assertNotIn(self.settings.api_key, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
