import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from app.engine import GenerationError, call_llm, generate_report, make_context, template_generate
from app.knowledge import KnowledgeBase
from app.models import GeneratedOutput, ReportRequest
from app.settings import DEFAULT_GEMINI_MODEL, get_settings, public_settings
from tests.test_domain import sample_case


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "settings.json"
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.settings_path = patch("app.settings.LOCAL_SETTINGS", self.path)
        self.settings_path.start()

    def tearDown(self):
        self.settings_path.stop()
        self.environment.stop()
        self.temp.cleanup()

    def test_default_gemini_is_unconfigured_without_key(self):
        config = get_settings()
        self.assertEqual(config.backend, "gemini")
        self.assertEqual(config.model, DEFAULT_GEMINI_MODEL)
        self.assertFalse(config.configured)

    def test_local_key_never_appears_in_public_settings_or_repr(self):
        self.path.write_text(json.dumps({"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "local-secret", "GEMINI_MODEL": "gemini-test"}))
        self.assertTrue(get_settings().configured)
        self.assertEqual(get_settings().credential_source, "local")
        self.assertNotIn("local-secret", repr(get_settings()))
        self.assertNotIn("local-secret", json.dumps(public_settings()))
        self.assertNotIn("api_key", public_settings())

    def test_environment_takes_priority_even_when_empty(self):
        self.path.write_text(json.dumps({"GEMINI_API_KEY": "saved-secret", "GEMINI_MODEL": "saved-model"}))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GEMINI_MODEL": "env-model"}):
            config = get_settings()
            self.assertFalse(config.configured)
            self.assertEqual(config.model, "env-model")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-secret"}):
            self.assertEqual(get_settings().credential_source, "environment")

    def test_legacy_openai_remains_usable(self):
        with patch.dict(os.environ, {"AI_API_KEY": "legacy-secret", "AI_MODEL": "legacy-model"}):
            config = get_settings()
            self.assertTrue(config.configured)
            self.assertEqual(config.backend, "openai")

    def test_explicit_gemini_does_not_use_legacy_key(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "gemini", "AI_API_KEY": "wrong-provider-secret", "AI_MODEL": "legacy-model"}):
            self.assertFalse(get_settings().configured)
            self.assertEqual(get_settings().api_key, "")

    def test_gemini_model_has_no_url_or_path_injection(self):
        for model in ("https://attacker.invalid/model", "../x", "gemini-test?key=value", "x/y", ""):
            with self.subTest(model=model), patch.dict(os.environ, {"GEMINI_API_KEY": "key", "GEMINI_MODEL": model}):
                self.assertFalse(get_settings().configured)
                self.assertIsNotNone(get_settings().error)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "key", "GEMINI_MODEL": "models/gemini-test"}):
            self.assertEqual(get_settings().model, "gemini-test")
            self.assertTrue(get_settings().configured)

    def test_malformed_local_file_fails_closed_without_echoing_content(self):
        self.path.write_text('{"GEMINI_API_KEY":"top-secret", invalid}')
        self.assertFalse(get_settings().configured)
        self.assertNotIn("top-secret", json.dumps(public_settings()))


class GeminiProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings_path = patch("app.settings.LOCAL_SETTINGS", Path(self.temp.name) / "missing.json")
        self.settings_path.start()
        self.environment = patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-gemini-secret", "GEMINI_MODEL": "gemini-test"}, clear=True)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.settings_path.stop()
        self.temp.cleanup()

    def context(self, **kwargs):
        return make_context(ReportRequest(case=sample_case(), **kwargs), self.kb)

    def payload(self, context=None):
        output = template_generate(context or self.context()).model_dump_json()
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": output}]}}],
                "modelVersion": "gemini-test-fixed-version", "responseId": "test-response",
                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 55, "totalTokenCount": 170, "thoughtsTokenCount": 15}}

    def invoke(self, response, context=None):
        with patch("app.engine.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            result = call_llm(context or self.context())
            return result, client.return_value.__enter__.return_value.post.call_args

    def test_native_endpoint_header_and_structured_schema(self):
        result, request = self.invoke(httpx.Response(200, json=self.payload()))
        self.assertEqual(request.args[0], "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent")
        self.assertNotIn("test-gemini-secret", request.args[0])
        self.assertNotIn("?", request.args[0])
        self.assertEqual(request.kwargs["headers"]["x-goog-api-key"], "test-gemini-secret")
        body = request.kwargs["json"]
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(body["generationConfig"]["responseJsonSchema"], GeneratedOutput.model_json_schema())
        self.assertEqual(body["generationConfig"]["temperature"], 0)
        self.assertIn("systemInstruction", body)
        self.assertEqual(result.findings[0].id, "F001")

    def test_usage_resolved_model_and_wire_hash_are_available(self):
        result, _ = self.invoke(httpx.Response(200, json=self.payload()))
        meta = result._generation_metadata
        self.assertEqual(meta["backend"], "gemini")
        self.assertEqual(meta["model_requested"], "gemini-test")
        self.assertEqual(meta["model_resolved"], "gemini-test-fixed-version")
        self.assertEqual(meta["usage"]["input_tokens"], 100)
        self.assertEqual(meta["usage"]["thought_tokens"], 15)
        self.assertEqual(len(meta["request_sha256"]), 64)
        self.assertNotIn("test-gemini-secret", json.dumps(meta))
        self.assertNotIn("_generation_metadata", result.model_dump())

    def test_report_records_gemini_provenance(self):
        with patch("app.engine.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = httpx.Response(200, json=self.payload())
            report = generate_report(ReportRequest(case=sample_case(), provider="llm"), self.kb)
        self.assertEqual(report["provenance"]["llm_backend"], "gemini")
        self.assertEqual(report["provenance"]["generation"]["model_resolved"], "gemini-test-fixed-version")
        self.assertNotIn("test-gemini-secret", json.dumps(report))

    def test_four_conditions_keep_same_model_and_isolate_context(self):
        marker = "UNIQUE-EVIDENCE-MARKER"
        case = sample_case()
        case["evidence"][0]["content"] = marker
        for grounding in (False, True):
            for rag in (False, True):
                with self.subTest(grounding=grounding, rag=rag):
                    context = make_context(ReportRequest(case=case, grounding=grounding, rag=rag), self.kb)
                    _, request = self.invoke(httpx.Response(200, json=self.payload(context)), context)
                    text = request.kwargs["json"]["contents"][0]["parts"][0]["text"]
                    self.assertEqual(marker in text, grounding)
                    sent = json.loads(text)["context"]
                    self.assertEqual(bool(sent["findings"][0]["owasp"]), rag)
                    self.assertIn("/gemini-test:generateContent", request.args[0])

    def test_thought_parts_are_not_parsed_as_json_output(self):
        payload = self.payload()
        payload["candidates"][0]["content"]["parts"].insert(0, {"text": "private reasoning, not JSON", "thought": True})
        output, _ = self.invoke(httpx.Response(200, json=payload))
        self.assertEqual(output.findings[0].id, "F001")

    def test_nonstop_and_blocked_responses_are_rejected(self):
        payloads = [{"promptFeedback": {"blockReason": "SAFETY"}}, {"candidates": []}]
        for reason in ("MAX_TOKENS", "SAFETY", "RECITATION", "CONTINUATION", None):
            value = self.payload()
            value["candidates"][0]["finishReason"] = reason
            payloads.append(value)
        for value in payloads:
            with self.subTest(payload=value), self.assertRaises(GenerationError):
                self.invoke(httpx.Response(200, json=value))

    def test_http_error_mapping_hides_response_and_does_not_retry(self):
        for status in (400, 401, 403, 404, 429, 500, 503):
            with self.subTest(status=status), patch("app.engine.httpx.Client") as client:
                post = client.return_value.__enter__.return_value.post
                post.return_value = httpx.Response(status, text="echoed-test-gemini-secret")
                with self.assertRaises(GenerationError) as error:
                    call_llm(self.context())
                self.assertEqual(error.exception.provider_status, status)
                self.assertEqual(error.exception.code, f"provider_http_{status}")
                self.assertNotIn("test-gemini-secret", str(error.exception))
                self.assertEqual(post.call_count, 1)

    def test_missing_key_and_invalid_model_do_not_make_network_calls(self):
        for overrides in ({"GEMINI_API_KEY": ""}, {"GEMINI_MODEL": "../elsewhere"}):
            with patch.dict(os.environ, overrides), patch("app.engine.httpx.Client") as client:
                with self.assertRaises(GenerationError):
                    call_llm(self.context())
                client.assert_not_called()

    def test_invalid_json_schema_and_empty_text_fail_closed(self):
        for text in ("", "not JSON", "{}", '{"findings":[]}'):
            payload = self.payload()
            payload["candidates"][0]["content"]["parts"][0]["text"] = text
            with self.subTest(text=text), self.assertRaises(GenerationError):
                self.invoke(httpx.Response(200, json=payload))

    def test_timeout_is_safe_and_not_retried(self):
        with patch("app.engine.httpx.Client") as client:
            post = client.return_value.__enter__.return_value.post
            post.side_effect = httpx.ReadTimeout("secret-provider-url?key=test-gemini-secret")
            with self.assertRaises(GenerationError) as error:
                call_llm(self.context())
            self.assertEqual(error.exception.code, "provider_timeout")
            self.assertNotIn("test-gemini-secret", str(error.exception))
            self.assertEqual(post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
