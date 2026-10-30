"""Project Pydantic JSON Schema onto Google's documented response subset.

The full schema still validates every response locally. This only removes
unsupported generation hints from the wire format; it does not relax acceptance.
Source: googleapis/python-genai, GenerateContentConfig.response_json_schema.
"""
from app.models import GeneratedOutput

SCHEMA_PROFILE = "gemini-supported-json-schema-v1"
SUPPORTED = {
    "$id", "$defs", "$ref", "$anchor", "type", "format", "title", "description",
    "enum", "items", "prefixItems", "minItems", "maxItems", "minimum", "maximum",
    "anyOf", "oneOf", "properties", "additionalProperties", "required", "propertyOrdering",
}


def gemini_response_schema() -> dict:
    def project(node):
        if not isinstance(node, dict):
            return node
        result = {}
        for key, value in node.items():
            if key not in SUPPORTED:
                continue
            if key in {"properties", "$defs"}:
                result[key] = {name: project(schema) for name, schema in value.items()}
            elif key in {"anyOf", "oneOf", "prefixItems"}:
                result[key] = [project(schema) for schema in value]
            elif key in {"items", "additionalProperties"}:
                result[key] = project(value)
            else:
                result[key] = value
        return result

    return project(GeneratedOutput.model_json_schema())
