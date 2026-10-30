import json
import os
import unittest
from copy import deepcopy
from unittest.mock import patch

import httpx

from app.engine import (
    GenerationError, call_llm, generate_report, make_context, structural_metrics,
    template_generate, validate_generated,
)
from app.knowledge import KnowledgeBase
from app.models import GeneratedOutput, ReportRequest
from tests.test_domain import sample_case


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()

    def context(self, **conditions):
        return make_context(ReportRequest(case=sample_case(), **conditions), self.kb)

    def test_four_conditions_respect_context_boundaries(self):
        evidence_marker = "PRIVATE-EVIDENCE-CONTENT-111"
        case = sample_case()
        case["evidence"][0]["content"] = evidence_marker
        for grounding in (False, True):
            for rag in (False, True):
                with self.subTest(grounding=grounding, rag=rag):
                    request = ReportRequest(case=case, grounding=grounding, rag=rag)
                    context = make_context(request, self.kb)
                    self.assertEqual(evidence_marker in json.dumps(context), grounding)
                    self.assertEqual(bool(context["findings"][0]["evidence"]), grounding)
                    self.assertEqual(bool(context["findings"][0]["owasp"]), rag)
                    report = generate_report(request, self.kb)
                    self.assertEqual(report["mode"], {"grounding": grounding, "rag": rag})
                    finding = report["findings"][0]
                    self.assertEqual(bool(finding["evidence_ids"]), grounding)
                    self.assertEqual(bool(finding["owasp"]), rag)
                    self.assertEqual(finding["status"], "supported" if grounding else "needs_review")
                    if not grounding:
                        self.assertEqual(finding["claims"], [])
                        self.assertNotIn(evidence_marker, json.dumps(report))
                    if not rag:
                        self.assertTrue(all(not r["owasp_refs"] for r in finding["remediation"]))

    def test_retrieval_is_identical_across_grounding_conditions(self):
        on = self.context(grounding=True)
        off = self.context(grounding=False)
        self.assertEqual(on["findings"][0]["owasp"], off["findings"][0]["owasp"])

    def test_missing_evidence_produces_abstention_not_confirmation(self):
        case = sample_case()
        case["evidence"] = []
        case["findings"][0]["evidence_ids"] = []
        report = generate_report(ReportRequest(case=case), self.kb)
        self.assertEqual(report["findings"][0]["claims"], [])
        self.assertEqual(report["findings"][0]["status"], "needs_review")
        self.assertEqual(report["summary"]["confirmed"], 0)
        self.assertEqual(report["summary"]["needs_review"], 1)

    def test_unknown_evidence_citation_is_rejected(self):
        context = self.context()
        output = template_generate(context).model_dump()
        output["findings"][0]["claims"][0]["evidence_ids"] = ["foreign-evidence"]
        with self.assertRaisesRegex(GenerationError, "unavailable"):
            validate_generated(GeneratedOutput.model_validate(output), context)

    def test_evidence_cannot_be_cited_from_another_finding(self):
        case = sample_case()
        case["findings"].append(dict(case["findings"][0], id="F002", evidence_ids=["E002"]))
        case["evidence"].append(dict(case["evidence"][0], id="E002", content="second finding only"))
        context = make_context(ReportRequest(case=case), self.kb)
        output = template_generate(context).model_dump()
        output["findings"][0]["claims"][0]["evidence_ids"] = ["E002"]
        with self.assertRaisesRegex(GenerationError, "unavailable"):
            validate_generated(GeneratedOutput.model_validate(output), context)

    def test_grounded_claim_without_citation_is_rejected(self):
        context = self.context()
        output = template_generate(context).model_dump()
        output["findings"][0]["claims"][0]["evidence_ids"] = []
        with self.assertRaisesRegex(GenerationError, "require evidence"):
            validate_generated(GeneratedOutput.model_validate(output), context)

    def test_unknown_owasp_citation_is_rejected(self):
        context = self.context()
        output = template_generate(context).model_dump()
        output["findings"][0]["remediation"][0]["owasp_refs"] = ["invented:001"]
        with self.assertRaisesRegex(GenerationError, "unavailable"):
            validate_generated(GeneratedOutput.model_validate(output), context)

    def test_rag_recommendation_without_source_is_rejected(self):
        context = self.context()
        output = template_generate(context).model_dump()
        output["findings"][0]["remediation"][0]["owasp_refs"] = []
        with self.assertRaisesRegex(GenerationError, "requires a retrieved source"):
            validate_generated(GeneratedOutput.model_validate(output), context)

    def test_condition_off_cannot_cite_hidden_context(self):
        for grounding, rag, field in ((False, True, "evidence"), (True, False, "owasp")):
            with self.subTest(field=field):
                context = self.context(grounding=grounding, rag=rag)
                output = template_generate(context).model_dump()
                if field == "evidence":
                    output["findings"][0]["claims"] = [{"text": "invented claim", "evidence_ids": ["E001"]}]
                else:
                    output["findings"][0]["remediation"][0]["owasp_refs"] = ["database:001"]
                with self.assertRaises(GenerationError):
                    validate_generated(GeneratedOutput.model_validate(output), context)

    def test_missing_or_duplicate_finding_is_rejected(self):
        context = self.context()
        output = template_generate(context).model_dump()
        wrong_id = deepcopy(output)
        wrong_id["findings"][0]["id"] = "NOT-THE-INPUT-ID"
        duplicate = deepcopy(output)
        duplicate["findings"].append(deepcopy(duplicate["findings"][0]))
        for result in (wrong_id, duplicate):
            with self.subTest(result=result):
                with self.assertRaisesRegex(GenerationError, "exactly once"):
                    validate_generated(GeneratedOutput.model_validate(result), context)

    def test_structural_metrics_do_not_claim_semantic_accuracy(self):
        report = generate_report(ReportRequest(case=sample_case()), self.kb)
        metrics = structural_metrics(report)
        self.assertEqual(metrics["finding_coverage"], 1.0)
        self.assertEqual(metrics["citation_validity"], 1.0)
        self.assertEqual(metrics["evidence_coverage"], 1.0)
        self.assertIsNone(metrics["unsupported_claim_rate"])
        self.assertEqual(report["provenance"]["semantic_validation"], "not_performed")

    def test_zero_citation_denominator_is_null_not_perfect(self):
        report = generate_report(ReportRequest(case=sample_case(), grounding=False, rag=False), self.kb)
        metrics = structural_metrics(report)
        self.assertIsNone(metrics["citation_validity"])
        self.assertIsNone(metrics["evidence_coverage"])
        self.assertEqual(metrics["counts"]["claims"], 0)

    def test_sensitive_input_is_redacted_before_context_and_report(self):
        case = sample_case()
        case["evidence"][0]["content"] = "password=do-not-leak; Authorization: Bearer keep-private"
        request = ReportRequest(case=case)
        context = make_context(request, self.kb)
        report = generate_report(request, self.kb)
        for data in (context, report):
            self.assertNotIn("do-not-leak", json.dumps(data))
            self.assertNotIn("keep-private", json.dumps(data))


class ProviderBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()

    def context(self):
        return make_context(ReportRequest(case=sample_case()), self.kb)

    def test_unconfigured_provider_does_not_attempt_network(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "AI_API_KEY": "", "AI_MODEL": ""}), patch("app.engine.httpx.Client") as client:
            with self.assertRaises(GenerationError):
                call_llm(self.context())
            client.assert_not_called()

    def test_non_https_provider_rejected_before_network(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "AI_API_KEY": "test-secret", "AI_MODEL": "test-model", "AI_BASE_URL": "http://provider.invalid/v1"}), patch("app.engine.httpx.Client") as client:
            with self.assertRaisesRegex(GenerationError, "HTTPS"):
                call_llm(self.context())
            client.assert_not_called()

    def test_successful_provider_output_is_parsed_without_network(self):
        context = self.context()
        output = template_generate(context).model_dump_json()
        response = httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": output}}]})
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "AI_API_KEY": "test-secret", "AI_MODEL": "test-model", "AI_BASE_URL": "https://provider.invalid/v1"}), patch("app.engine.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            parsed = call_llm(context)
            validate_generated(parsed, context)
            request = client.return_value.__enter__.return_value.post.call_args
            self.assertEqual(request.args[0], "https://provider.invalid/v1/chat/completions")
            self.assertEqual(request.kwargs["json"]["model"], "test-model")
            self.assertEqual(request.kwargs["json"]["temperature"], 0)

    def test_incomplete_provider_output_is_rejected(self):
        response = httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]})
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "AI_API_KEY": "test-secret", "AI_MODEL": "test-model", "AI_BASE_URL": "https://provider.invalid/v1"}), patch("app.engine.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            with self.assertRaisesRegex(GenerationError, "incomplete"):
                call_llm(self.context())

    def test_provider_error_omits_sensitive_response_body(self):
        response = httpx.Response(401, text="accidentally-echoed-secret")
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "AI_API_KEY": "test-secret", "AI_MODEL": "test-model", "AI_BASE_URL": "https://provider.invalid/v1"}), patch("app.engine.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            with self.assertRaises(GenerationError) as error:
                call_llm(self.context())
            self.assertIn("401", str(error.exception))
            self.assertNotIn("accidentally-echoed-secret", str(error.exception))
            self.assertNotIn("test-secret", str(error.exception))


if __name__ == "__main__":
    unittest.main()
