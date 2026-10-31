#!/usr/bin/env python3
"""Run all four conditions; collect outputs, not invented research scores."""
import argparse
import csv
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine import GenerationError, generate_report, llm_configured, structural_metrics
from app.knowledge import KnowledgeBase
from app.models import Case, ReportRequest
from app.settings import public_settings
from app.research import REVIEW_FIELDS, blank_review_row


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "data" / "cases")
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing paths are never overwritten")
    parser.add_argument("--provider", choices=["template", "llm"], default="template")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--seed", type=int, default=491)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("repeats must be between 1 and 20")
    if args.provider == "llm" and not llm_configured():
        parser.error("Configure Gemini using run.py --configure-gemini, or set GEMINI_API_KEY and GEMINI_MODEL; template runs cannot answer LLM RQs")
    paths = sorted(args.cases.glob("*.json"))
    if not paths:
        parser.error("No JSON cases found")
    cases = [(p.stem, Case.model_validate_json(p.read_text(encoding="utf-8"))) for p in paths]
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "reports").mkdir()
    tasks = [(name, case, repeat, g, r) for name, case in cases
             for repeat in range(args.repeats) for g in (False, True) for r in (False, True)]
    random.Random(args.seed).shuffle(tasks)
    frozen_settings = public_settings() if args.provider == "llm" else None
    manifest = {"provider": args.provider, "seed": args.seed, "repeats": args.repeats,
                "llm": frozen_settings,
                "interpretation": "software smoke baseline only" if args.provider == "template" else "LLM outputs awaiting independent expert assessment",
                "case_hashes": {name: hashlib.sha256(case.model_dump_json().encode()).hexdigest() for name, case in cases},
                "conditions": {"G": "evidence access plus citation/abstention instructions", "R": "OWASP BM25 context plus source-citation instructions"},
                "planned_runs": len(tasks), "owasp_sources": KnowledgeBase().sources}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    kb = KnowledgeBase()
    failures = 0
    review_rows = []
    with (args.output / "runs.jsonl").open("w", encoding="utf-8") as runs:
        for order, (name, case, repeat, grounding, rag) in enumerate(tasks):
            blind_id = f"B{order + 1:04d}"
            row = {"blind_id": blind_id, "case_id": name, "repeat": repeat,
                   "grounding": grounding, "rag": rag, "provider": args.provider, "order": order}
            start = time.perf_counter()
            try:
                if frozen_settings:
                    current = public_settings()
                    if tuple(current.get(k) for k in ("backend", "model", "schema_mode")) != tuple(frozen_settings.get(k) for k in ("backend", "model", "schema_mode")):
                        raise GenerationError("Model or schema mode changed during this run; API call skipped.", code="configuration_changed")
                report = generate_report(ReportRequest(case=case, grounding=grounding, rag=rag, provider=args.provider), kb)
                row.update(status="completed", report_id=report["id"], structural=structural_metrics(report),
                           generation=report["provenance"].get("generation", {}))
                (args.output / "reports" / f"{blind_id}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
                (args.output / "reports" / f"{blind_id}.md").write_text(report["markdown"], encoding="utf-8")
                for finding in report["findings"]:
                    review_rows.append(blank_review_row(blind_id, finding["id"], "finding"))
                    for remediation_index, _ in enumerate(finding["remediation"], start=1):
                        review_rows.append(blank_review_row(blind_id, finding["id"], "remediation", remediation_index))
            except Exception as exc:
                failures += 1
                # Do not log provider responses or credentials.
                row.update(status="failed", error_type=type(exc).__name__,
                           error_code=getattr(exc, "code", "generation_failed"),
                           provider_status=getattr(exc, "provider_status", None),
                           diagnostic=getattr(exc, "diagnostic", None))
            row["latency_seconds"] = round(time.perf_counter() - start, 4)
            runs.write(json.dumps(row, ensure_ascii=False) + "\n")
            runs.flush()
            print(f"{blind_id}: {name} G={int(grounding)} R={int(rag)} {row['status']}")
    with (args.output / "expert-review.csv").open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(review_rows)
    print(f"{len(tasks) - failures}/{len(tasks)} runs completed. Expert scores remain blank. Failures: {failures}.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
