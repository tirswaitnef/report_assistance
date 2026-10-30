import json
import unittest

import httpx

from app.gemini_diagnostics import gemini_error_hint


class GeminiDiagnosticsTests(unittest.TestCase):
    def hint(self, error):
        return gemini_error_hint(httpx.Response(400, json={"error": error}))

    def test_schema_field_violation_exposes_only_canonical_root(self):
        hint = self.hint({"status": "INVALID_ARGUMENT", "message": "Sensitive echoed content",
                          "details": [{"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [
                              {"field": "generation_config.response_json_schema.properties.private_data", "description": "password=secret-value"},
                              {"field": "generationConfig.responseJsonSchema.properties.another_secret", "description": "x-goog-api-key: private-value"},
                              {"field": "customer_secret_field", "description": "Bearer credential"}]}]})
        self.assertEqual(hint["kind"], "invalid_schema")
        self.assertEqual(hint["fields"], ["generationConfig.responseJsonSchema"])
        self.assertNotIn("secret", json.dumps(hint))
        self.assertNotIn("Sensitive", json.dumps(hint))
        self.assertNotIn("private", json.dumps(hint))

    def test_temperature_error_without_field_violations(self):
        hint = self.hint({"status": "INVALID_ARGUMENT", "message": "temperature must be within range [0, 2]; echoed_key=private"})
        self.assertEqual(hint["kind"], "invalid_temperature")
        self.assertEqual(hint["fields"], [])
        self.assertNotIn("echoed_key", json.dumps(hint))

    def test_unsupported_model_or_endpoint(self):
        for message in ("This model is not supported for generateContent", "models/customer-private-model not found", "generateContent is not supported"):
            with self.subTest(message=message):
                self.assertEqual(self.hint({"message": message})["kind"], "invalid_model")

    def test_invalid_key_is_safely_classified_from_error_info(self):
        hint = self.hint({"message": "https://example.invalid?key=never-echo-this", "details": [
            {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID", "metadata": {"key": "never-echo-this"}}]})
        self.assertEqual(hint["kind"], "invalid_api_key")
        self.assertNotIn("never-echo-this", json.dumps(hint))
        self.assertNotIn("example.invalid", json.dumps(hint))

    def test_token_limit_does_not_match_an_arbitrary_token_word(self):
        self.assertEqual(self.hint({"message": "The input token count exceeds the allowed limit"})["kind"], "token_limit")
        self.assertEqual(self.hint({"message": "token=private-value"})["kind"], "invalid_argument")

    def test_region_or_billing_hint(self):
        for message in ("User location is not supported", "Billing is required"):
            self.assertEqual(self.hint({"message": message})["kind"], "region_or_billing")

    def test_malformed_nonjson_and_oversized_errors_are_generic(self):
        responses = [httpx.Response(400, text="not JSON key=do-not-show"),
                     httpx.Response(400, json=[]), httpx.Response(400, json={"error": []}),
                     httpx.Response(400, text="sensitive" * 10000)]
        for response in responses:
            with self.subTest(size=len(response.content)):
                hint = gemini_error_hint(response)
                self.assertEqual(hint["kind"], "invalid_argument")
                self.assertEqual(hint["fields"], [])
                self.assertNotIn("sensitive", json.dumps(hint))

    def test_malicious_field_names_are_not_reflected(self):
        hint = self.hint({"message": "<script>alert('secret')</script>", "details": [
            {"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": [
                {"field": "https://example.invalid/?generationConfig.temperature=secret"},
                {"field": "unknown.generation_config.response_json_schema"},
                {"field": "generationConfig.responseJsonSchemaSecretSuffix"}]}]})
        self.assertEqual(hint["kind"], "invalid_argument")
        self.assertEqual(hint["fields"], [])

    def test_unknown_detail_shapes_do_not_raise(self):
        for details in (None, "secret", [None, "private", {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": ["malformed"]}, {"@type": "type.googleapis.com/google.rpc.BadRequest", "fieldViolations": "bad-shape"}]):
            with self.subTest(details=details):
                self.assertEqual(self.hint({"message": None, "details": details})["kind"], "invalid_argument")


if __name__ == "__main__":
    unittest.main()
