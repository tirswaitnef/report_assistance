"""Project Pydantic JSON Schema onto Google's documented response subset.

The full schema still validates every response locally. This only removes
unsupported generation hints from the wire format; it does not relax acceptance.
Source: googleapis/python-genai, GenerateContentConfig.response_json_schema.
"""
from app.models import GeneratedOutput

SCHEMA_PROFILE = "gemini-supported-json-schema-v1"
TYPED_SCHEMA_PROFILE = "gemini-inline-response-schema-v1"
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


def gemini_typed_response_schema() -> dict:
    """Inline our report schema into the native Schema subset.

    Only structural output hints are sent. Full size/extra-field constraints
    continue to be enforced by GeneratedOutput after receiving the response.
    """
    schema = GeneratedOutput.model_json_schema()
    definitions = schema.get("$defs", {})
    supported_types = {"object": "OBJECT", "array": "ARRAY", "string": "STRING"}

    def convert(node, stack=()):
        if not isinstance(node, dict):
            raise ValueError("Invalid generated report schema")
        if "$ref" in node:
            reference = node["$ref"]
            if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
                raise ValueError("Only local report schema references are supported")
            name = reference.removeprefix("#/$defs/")
            if name not in definitions or name in stack:
                raise ValueError("Missing or recursive report schema reference")
            return convert(definitions[name], (*stack, name))
        kind = node.get("type")
        if kind not in supported_types:
            raise ValueError("Unsupported generated report schema type")
        result = {"type": supported_types[kind]}
        if kind == "object":
            properties = node.get("properties", {})
            if not isinstance(properties, dict):
                raise ValueError("Invalid report schema properties")
            result["properties"] = {name: convert(value, stack) for name, value in properties.items()}
            if "required" in node:
                result["required"] = list(node["required"])
        elif kind == "array":
            result["items"] = convert(node.get("items"), stack)
        return result

    return convert(schema)


def gemini_schema_profile(mode: str) -> str:
    if mode == "typed":
        return TYPED_SCHEMA_PROFILE
    if mode == "json_schema":
        return SCHEMA_PROFILE
    raise ValueError("GEMINI_SCHEMA_MODE must be typed or json_schema")


def gemini_format(mode: str) -> dict:
    """Select one declared wire format, without retries or fallbacks."""
    if mode == "typed":
        return {"responseMimeType": "application/json", "responseSchema": gemini_typed_response_schema()}
    if mode == "json_schema":
        return {"responseMimeType": "application/json", "responseJsonSchema": gemini_response_schema()}
    raise ValueError("GEMINI_SCHEMA_MODE must be typed or json_schema")
