#!/usr/bin/env python3
"""Check the configured model with metadata and one synthetic report request."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from app.engine import GenerationError, call_llm, provider_response_error, validate_generated
from app.settings import get_settings


def run():
    settings = get_settings()
    if settings.backend != "gemini" or not settings.configured:
        print("Gemini is not configured. Run: py -3.12 run.py --configure-gemini")
        return 1
    print("Gemini diagnostic: model =", settings.model)
    print("No key, local settings or database evidence will be printed.")
    endpoint = f"{settings.base_url}/models/{settings.model}"
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=15), follow_redirects=False) as client:
            response = client.get(endpoint, headers={"x-goog-api-key": settings.api_key})
        print("Model metadata HTTP:", response.status_code)
        if response.status_code != 200:
            raise provider_response_error(response, "gemini")
        metadata = response.json()
        methods = metadata.get("supportedGenerationMethods", [])
        if isinstance(methods, list):
            print("generateContent listed:", "generateContent" in methods)
        print("Sending ONE synthetic structured-output check. This may consume API quota.")
        context = {"title": "Synthetic connectivity check", "database": "PostgreSQL", "grounding": True, "rag": False,
                   "findings": [{"id": "DIAG-001", "title": "Missing evidence", "category": "other",
                                 "severity": "info", "description": "Synthetic test; no evidence is available. Abstain from factual vulnerability claims.",
                                 "asset": "synthetic-lab", "evidence_ids": [], "evidence": [], "owasp": []}]}
        output = call_llm(context)
        validate_generated(output, context)
        print("Structured output and citation guards: PASS")
        generation = output._generation_metadata
        print("Schema profile:", generation.get("schema_profile"))
        print("Returned model version:", generation.get("model_resolved") or "not supplied")
        print("Token usage:", json.dumps(generation.get("usage", {})))
        print("This is a connection test, not a research result. Return to the web app to generate a report.")
        return 0
    except GenerationError as exc:
        print("FAILED:", str(exc))
        print("Safe error code:", exc.code)
        if exc.diagnostic:
            print("Safe diagnostic:", json.dumps(exc.diagnostic, ensure_ascii=True))
        return 1
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        print("FAILED: Network or metadata format error. Raw response withheld. Check Internet and configured model ID.")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
