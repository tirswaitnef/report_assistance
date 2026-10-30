import copy
import unittest

from pydantic import ValidationError

from app.gemini_schema import gemini_response_schema, SUPPORTED
from app.models import GeneratedOutput


class GeminiSchemaTests(unittest.TestCase):
    def test_wire_schema_uses_supported_keywords_and_resolves_all_references(self):
        schema = gemini_response_schema()
        def walk(node):
            self.assertTrue(set(node) <= SUPPORTED)
            self.assertNotIn("default", node)
            self.assertNotIn("minLength", node)
            self.assertNotIn("maxLength", node)
            if "$ref" in node:
                self.assertIn(node["$ref"].removeprefix("#/$defs/"), schema["$defs"])
            for group in ("properties", "$defs"):
                for value in node.get(group, {}).values():
                    walk(value)
            if isinstance(node.get("items"), dict):
                walk(node["items"])
        walk(schema)
        self.assertEqual(schema["required"], ["findings"])
        self.assertIs(schema["additionalProperties"], False)

    def test_projection_does_not_mutate_local_schema_or_relax_validation(self):
        original = copy.deepcopy(GeneratedOutput.model_json_schema())
        gemini_response_schema()
        self.assertEqual(GeneratedOutput.model_json_schema(), original)
        self.assertEqual(original["$defs"]["GeneratedFinding"]["properties"]["analysis"]["maxLength"], 6000)
        for analysis in ("", "x" * 6001):
            with self.subTest(length=len(analysis)), self.assertRaises(ValidationError):
                GeneratedOutput.model_validate({"findings": [{"id": "F1", "analysis": analysis}]})
        with self.assertRaises(ValidationError):
            GeneratedOutput.model_validate({"findings": [{"id": "F1", "analysis": "Valid", "invented": True}]})


if __name__ == "__main__":
    unittest.main()
