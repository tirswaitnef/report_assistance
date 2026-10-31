#!/usr/bin/env python3
"""Isolate native Gemini request parameters using synthetic inputs only."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from app.engine import SYSTEM_PROMPT
from app.gemini_schema import gemini_response_schema
from app.privacy import redact
from app.settings import get_settings


def inline_schema(schema):
    definitions = schema.get("$defs", {})
    def visit(value, stack=()):
        if isinstance(value, list):
            return [visit(item, stack) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            name = value["$ref"].removeprefix("#/$defs/")
            if name not in definitions or name in stack:
                raise ValueError("Unsupported schema reference")
            return visit(definitions[name], stack + (name,))
        return {key: visit(item, stack) for key, item in value.items() if key != "$defs"}
    return visit(schema)


def typed_schema(schema):
    result = {}
    if "type" in schema:
        result["type"] = schema["type"].upper()
    if "properties" in schema:
        result["properties"] = {key: typed_schema(value) for key, value in schema["properties"].items()}
    if "items" in schema:
        result["items"] = typed_schema(schema["items"])
    if "required" in schema:
        result["required"] = list(schema["required"])
    return result


def build_probes():
    def body(text, config=None, system=None):
        value = {"contents": [{"role": "user", "parts": [{"text": text}]}]}
        if config is not None:
            value["generationConfig"] = copy.deepcopy(config)
        if system is not None:
            value["systemInstruction"] = {"parts": [{"text": system}]}
        return value
    text = "Reply only with OK. This is a synthetic connection check."
    schema = gemini_response_schema()
    report_text = 'Return one synthetic finding: id DIAG-001, analysis "No evidence supplied", claims [], remediation []. No real database is involved.'
    context = {"title": "Synthetic connectivity check", "database": "PostgreSQL", "grounding": True, "rag": False,
               "findings": [{"id": "DIAG-001", "title": "Missing evidence", "category": "other", "severity": "info",
                             "description": "Synthetic test; no evidence is available. Abstain from factual vulnerability claims.",
                             "asset": "synthetic-lab", "evidence_ids": [], "evidence": [], "owasp": []}]}
    mime = {"responseMimeType": "application/json"}
    return [
        {"name": "text_minimal", "body": body(text)},
        {"name": "temp_zero", "body": body(text, {"temperature": 0})},
        {"name": "max_output_tokens", "body": body(text, {"maxOutputTokens": 8192})},
        {"name": "json_mime", "body": body('Return only JSON: {"ok":true}', mime)},
        {"name": "json_schema_minimal", "body": body('Return {"ok":true}', {**mime, "responseJsonSchema": {
            "type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}})},
        {"name": "report_json_schema", "body": body(report_text, {**mime, "responseJsonSchema": schema})},
        {"name": "inline_report_schema", "conditional": True, "body": body(report_text, {**mime, "responseJsonSchema": inline_schema(schema)})},
        {"name": "typed_report_schema", "conditional": True, "body": body(report_text, {**mime, "responseSchema": typed_schema(inline_schema(schema))})},
        {"name": "system_instruction", "body": body(text, system=SYSTEM_PROMPT)},
        {"name": "application_request", "body": body(json.dumps({"context": context}, ensure_ascii=False),
            {**mime, "temperature": 0, "maxOutputTokens": 8192, "responseJsonSchema": schema}, SYSTEM_PROMPT)},
    ]


def safe_error(response, key):
    if len(response.content) > 65536:
        return {"message": "Error response exceeds diagnostic size limit"}
    try:
        payload = response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message", "No JSON error message") if isinstance(error, dict) else "No JSON error message"
        if not isinstance(message, str):
            message = "Non-text error message"
        if key:
            message = message.replace(key, "[REDACTED]")
        return {"message": redact(message)[:2000]}
    except ValueError:
        return {"message": "Non-JSON error; response omitted"}


def run(only=None):
    probes = build_probes()
    if only and only not in {probe["name"] for probe in probes}:
        print("Unknown probe name. Use --help for choices.", flush=True)
        return 2
    settings = get_settings()
    if settings.backend != "gemini" or not settings.configured:
        print("Gemini is not configured. Run: py -3.12 run.py --configure-gemini", flush=True)
        return 2
    print("GEMINI DIRECT PROBE v1 | model:", settings.model, flush=True)
    print("Synthetic prompts only; no findings, evidence or keys are printed.", flush=True)
    print("API calls can consume quota. Maximum calls:", 1 if only else 10, flush=True)
    results = []
    schema_failed = False
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.model}:generateContent"
    try:
        with httpx.Client(timeout=httpx.Timeout(60, connect=15), follow_redirects=False) as client:
            for probe in probes:
                if only and probe["name"] != only:
                    continue
                if not only and probe.get("conditional") and not schema_failed:
                    continue
                name = probe["name"]
                print("PROBE", name, "sending...", flush=True)
                row = {"name": name, "request_sha256": hashlib.sha256(json.dumps(probe["body"], sort_keys=True).encode()).hexdigest()}
                try:
                    response = client.post(endpoint, json=probe["body"], headers={"x-goog-api-key": settings.api_key})
                    row["http_status"] = response.status_code
                    row["accepted"] = response.status_code == 200
                    print("PROBE", name, "HTTP", response.status_code, flush=True)
                    if not row["accepted"]:
                        row["error"] = safe_error(response, settings.api_key)
                        print("GOOGLE_ERROR:", row["error"]["message"], flush=True)
                    results.append(row)
                    if name == "report_json_schema":
                        schema_failed = not row["accepted"]
                    if response.status_code in {401, 403, 404, 429} or (name == "text_minimal" and not row["accepted"]):
                        print("Stopping: resolve baseline/access/quota failure before further calls.", flush=True)
                        break
                except httpx.HTTPError:
                    row.update(accepted=False, error={"message": "Network/timeout error; raw exception withheld"})
                    results.append(row)
                    print("PROBE", name, "NETWORK_ERROR; stopping.", flush=True)
                    break
    finally:
        folder = ROOT / ".local" / "diagnostics"
        folder.mkdir(parents=True, exist_ok=True)
        report = {"version": "direct-probe-v1", "model": settings.model,
                  "created_at": datetime.now(timezone.utc).isoformat(), "results": results,
                  "interpretation": "HTTP200 means parameter acceptance only, not report correctness; no research scores."}
        path = folder / f"probe-{uuid4().hex[:12]}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("SUMMARY:", " | ".join(f"{row['name']}={row.get('http_status', 'NETWORK_ERROR')}" for row in results), flush=True)
        print("Sanitized report saved in .local/diagnostics/", flush=True)
    return 0 if results and all(row["accepted"] for row in results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=[probe["name"] for probe in build_probes()], help="Send only one named probe")
    args = parser.parse_args()
    raise SystemExit(run(args.only))
