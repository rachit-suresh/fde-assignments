"""
End-to-End Agent Workflow Integration Tests for FDE Assessment 3.
Verifies:
1. Architecture A & Architecture B execution and contract validity.
2. Real LLM invocation and telemetry tracking when API key is active.
3. Policy enforcement: Budget check, prompt injection containment, service outage handling.
4. Output parser robustness with various markdown formats.
"""
from __future__ import annotations

import unittest
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.contracts import ProcurementDecision
from src.solution import handle_request
from src.llm_client import parse_llm_recommendation
from src.policy_engine import detect_prompt_injection


class AgentWorkflowIntegrationTests(unittest.TestCase):
    def test_single_agent_contract_and_telemetry(self):
        """REQ-1001: Verifies single agent produces valid ProcurementDecision with tools and LLM telemetry."""
        dec = handle_request("REQ-1001", architecture="single")
        self.assertIsInstance(dec, ProcurementDecision)
        self.assertEqual(dec.request_id, "REQ-1001")
        self.assertIn("Manager", dec.required_approvals)
        self.assertTrue(dec.human_review_required)
        self.assertGreaterEqual(len(dec.evidence), 4)
        self.assertGreaterEqual(dec.telemetry.tool_calls, 4)
        
        has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        if has_key:
            self.assertGreaterEqual(dec.telemetry.llm_calls, 1, "Expected at least 1 real LLM invocation in Architecture A")

    def test_staged_agent_contract_and_telemetry(self):
        """REQ-1001: Verifies staged agent produces valid ProcurementDecision with 2-stage LLM telemetry."""
        dec = handle_request("REQ-1001", architecture="staged")
        self.assertIsInstance(dec, ProcurementDecision)
        self.assertEqual(dec.request_id, "REQ-1001")
        self.assertIn("Manager", dec.required_approvals)
        self.assertTrue(dec.human_review_required)
        self.assertGreaterEqual(len(dec.evidence), 4)
        
        has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        if has_key:
            self.assertGreaterEqual(dec.telemetry.llm_calls, 2, "Expected at least 2 real LLM invocations in Architecture B")

    def test_prompt_injection_containment(self):
        """REQ-1006: Verifies adversarial prompt injection is quarantined and policy cannot be bypassed."""
        dec = handle_request("REQ-1006", architecture="single")
        self.assertIn("prompt_injection_detected", dec.risk_flags)
        self.assertIn("missing_information", dec.risk_flags)
        self.assertTrue(dec.human_review_required)
        # Ensure that untrusted user prompt did not succeed in auto-approving
        self.assertNotIn("cfo-approved", dec.recommendation.lower())

    def test_service_outage_resilience(self):
        """REQ-1009: Verifies 503 upstream API outage degrades gracefully into security review."""
        dec = handle_request("REQ-1009", architecture="single")
        self.assertIn("vendor_risk_unavailable", dec.risk_flags)
        self.assertIn("security_review_required", dec.risk_flags)
        self.assertIn("Security", dec.required_approvals)
        self.assertTrue(dec.human_review_required)

    def test_budget_shortfall_enforcement(self):
        """REQ-1005: Verifies budget deficit flags budget_insufficient and routes to Finance."""
        dec = handle_request("REQ-1005", architecture="single")
        self.assertIn("budget_insufficient", dec.risk_flags)
        self.assertIn("Finance", dec.required_approvals)
        self.assertTrue(dec.human_review_required)

    def test_parse_llm_recommendation_robustness(self):
        """Verifies markdown stripping and pattern extraction from various LLM response formats."""
        t_markdown = "**RECOMMENDATION:** Approve subject to compliance.\n**NEXT_STEP:** Route to Noah."
        rec, nxt = parse_llm_recommendation(t_markdown, "f_rec", "f_nxt")
        self.assertEqual(rec, "Approve subject to compliance.")
        self.assertEqual(nxt, "Route to Noah.")

        t_plain = "RECOMMENDATION: Put on hold.\nNEXT_STEP: Escalate to Security."
        rec, nxt = parse_llm_recommendation(t_plain, "f_rec", "f_nxt")
        self.assertEqual(rec, "Put on hold.")
        self.assertEqual(nxt, "Escalate to Security.")

        t_freeform = "The request is within budget and compliant.\nSubmit for manager authorization."
        rec, nxt = parse_llm_recommendation(t_freeform, "f_rec", "f_nxt")
        self.assertEqual(rec, "The request is within budget and compliant.")
        self.assertEqual(nxt, "Submit for manager authorization.")


    def test_conflicting_vendor_evidence_and_expired_review(self):
        """REQ-1007: Verifies registry vs vendor risk conflict and expired review (>365d) triggers security review."""
        dec = handle_request("REQ-1007", architecture="single")
        self.assertIn("conflicting_vendor_evidence", dec.risk_flags)
        self.assertIn("vendor_review_expired", dec.risk_flags)
        self.assertIn("security_review_required", dec.risk_flags)
        self.assertIn("Security", dec.required_approvals)
        self.assertTrue(dec.human_review_required)

    def test_competing_software_overlap(self):
        """REQ-1002: Verifies new vendor in existing category triggers existing_tool_overlap and legal review."""
        dec = handle_request("REQ-1002", architecture="single")
        self.assertIn("existing_tool_overlap", dec.risk_flags)
        self.assertIn("legal_review_required", dec.risk_flags)
        self.assertIn("security_review_required", dec.risk_flags)
        self.assertIn("Department Head", dec.required_approvals)
        self.assertIn("Procurement", dec.required_approvals)
        self.assertTrue(dec.human_review_required)

    def test_financial_approval_threshold_brackets(self):
        """Verifies deterministic dollar threshold brackets from Policy Section 4."""
        from src.policy_engine import evaluate_financial_approvals
        # Up to $1,000: Manager
        self.assertEqual(evaluate_financial_approvals(500), ["Manager"])
        self.assertEqual(evaluate_financial_approvals(1000), ["Manager"])
        # $1,000.01 - $10,000: Department Head + Procurement
        self.assertEqual(evaluate_financial_approvals(1000.01), ["Department Head", "Procurement"])
        self.assertEqual(evaluate_financial_approvals(10000), ["Department Head", "Procurement"])
        # $10,000.01 - $25,000: Department Head + Finance + Procurement
        self.assertEqual(evaluate_financial_approvals(10000.01), ["Department Head", "Finance", "Procurement"])
        self.assertEqual(evaluate_financial_approvals(25000), ["Department Head", "Finance", "Procurement"])
        # Above $25,000: Department Head + Finance + CFO + Procurement
        self.assertEqual(evaluate_financial_approvals(25000.01), ["Department Head", "Finance", "CFO", "Procurement"])
        self.assertEqual(evaluate_financial_approvals(100000), ["Department Head", "Finance", "CFO", "Procurement"])


if __name__ == "__main__":
    unittest.main()
