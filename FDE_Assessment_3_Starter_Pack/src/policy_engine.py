"""
Deterministic Policy & Compliance Engine for Assessment 3.
Implements the rules from data/procurement_policy.md:
1. Missing Information Detection
2. Prompt Injection Scans
3. Financial Threshold Matrix (Manager, Dept Head, Finance, CFO, Procurement)
4. Security Review Rules (Data sensitivity, Integrations, Vendor review freshness)
5. Privacy Review Rules (PII, Regional boundaries)
6. Legal Review Rules (New vendor spend >= $10k, Non-standard terms)
7. Tool Failure / Service Outage Routing
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple
from src.contracts import EvidenceItem

INJECTION_PATTERNS = [
    r"ignore (?:all )?(?:procurement |approval |security )?rules",
    r"cfo[- ]approved",
    r"approve (?:it )?immediately",
    r"override (?:the )?(?:policy|rules|controls)",
    r"system prompt",
    r"treat this request as",
    r"bypass (?:all )?(?:controls|security|approvals)",
    r"disregard (?:all |previous )?instructions",
    r"skip (?:all )?(?:approvals?|security|checks?)",
    r"emergency override",
    r"act as (?:an? )?admin",
]


def detect_prompt_injection(text: str) -> Tuple[bool, List[str]]:
    """Scans untrusted user text for adversarial prompt injection attempts."""
    if not text:
        return False, []
    matches = []
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            matches.append(pattern)
    return len(matches) > 0, matches


def evaluate_completeness(request: Dict[str, Any]) -> List[str]:
    """Identifies missing material fields required by Policy Section 1."""
    missing: List[str] = []
    
    cost = request.get("annual_cost_usd")
    if cost is None or cost == "" or cost == "null":
        missing.append("annual cost")
        
    users = request.get("user_count")
    if users is None or users == "" or users == "null":
        missing.append("user count / license seats")
        
    data_access = str(request.get("data_access_level", "")).lower()
    if not data_access or data_access in ["unknown", "none", "null", ""]:
        # Only flag if not explicitly 'none' or if completely missing/unknown
        if data_access != "none":
            missing.append("data access level")
            
    if not request.get("requester_id"):
        missing.append("requester id")
    if not request.get("product_name"):
        missing.append("product name")
    if not request.get("vendor_name"):
        missing.append("vendor name")
        
    return missing


def evaluate_financial_approvals(annual_cost: float | None) -> List[str]:
    """
    Enforces deterministic financial approval tiers from Policy Section 4:
    - Up to $1,000: Manager
    - $1,000.01 - $10,000: Department Head + Procurement
    - $10,000.01 - $25,000: Department Head + Finance + Procurement
    - Above $25,000: Department Head + Finance + CFO + Procurement
    """
    if annual_cost is None:
        # If cost is missing, minimum business review is required
        return ["Manager", "Department Head"]
        
    cost = float(annual_cost)
    if cost <= 1000.0:
        return ["Manager"]
    elif cost <= 10000.0:
        return ["Department Head", "Procurement"]
    elif cost <= 25000.0:
        return ["Department Head", "Finance", "Procurement"]
    else:
        return ["Department Head", "Finance", "CFO", "Procurement"]


def evaluate_policy_compliance(
    request: Dict[str, Any],
    budget_result: Dict[str, Any],
    catalog_result: Dict[str, Any],
    vendor_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates complete deterministic policy rules combining tool facts and request metadata.
    Returns:
    - risk_flags: List[str]
    - required_approvals: List[str]
    - missing_information: List[str]
    - policy_evidence: List[EvidenceItem]
    """
    risk_flags: Set[str] = set()
    approvals: Set[str] = set()
    evidence_items: List[EvidenceItem] = []
    
    # 1. Missing Information
    missing_info = evaluate_completeness(request)
    if missing_info:
        risk_flags.add("missing_information")
        evidence_items.append(EvidenceItem(
            source="policy_completeness_check",
            finding=f"Material request information missing: {', '.join(missing_info)}.",
            reference="procurement_policy.md#1"
        ))
        
    # 2. Prompt Injection Detection
    justification = str(request.get("business_justification", ""))
    is_injected, matched_patterns = detect_prompt_injection(justification)
    if is_injected:
        risk_flags.add("prompt_injection_detected")
        evidence_items.append(EvidenceItem(
            source="security_input_sanitizer",
            finding=f"Adversarial prompt injection pattern detected in business justification: '{matched_patterns[0]}'. Request instructions quarantined.",
            reference="procurement_policy.md#9"
        ))

    # 3. Budget Check
    annual_cost = request.get("annual_cost_usd")
    if annual_cost is not None:
        cost = float(annual_cost)
        if not budget_result.get("is_sufficient", True):
            risk_flags.add("budget_insufficient")
            approvals.add("Finance")
            evidence_items.append(EvidenceItem(
                source="budget_policy_gate",
                finding=f"Budget breach: Request (${cost:,.2f}) exceeds available department budget by ${budget_result.get('requested_cost_usd', 0) - budget_result.get('available_usd', 0):,.2f}.",
                reference="procurement_policy.md#2"
            ))

    # 4. Catalog Overlap Check
    if catalog_result.get("has_overlap"):
        risk_flags.add("existing_tool_overlap")
        evidence_items.append(EvidenceItem(
            source="catalog_overlap_policy",
            finding=f"Existing approved tools overlap with this request. Requires justification before net-new tool onboarding.",
            reference="procurement_policy.md#3"
        ))

    # 5. Financial Approvals Base Matrix
    base_financial_approvals = evaluate_financial_approvals(annual_cost)
    for app in base_financial_approvals:
        approvals.add(app)

    # 6. Vendor API Availability Gate
    if not vendor_result.get("api_available", True):
        risk_flags.add("vendor_risk_unavailable")
        risk_flags.add("security_review_required")
        approvals.add("Security")
        approvals.add("Finance")
        approvals.add("Legal")
        evidence_items.append(EvidenceItem(
            source="vendor_risk_availability_gate",
            finding=f"External vendor risk API is unavailable. Mandatory security, legal, and financial escrow review required.",
            reference="procurement_policy.md#10"
        ))

    # 7. Security Review Gate (Policy Section 5)
    data_access = str(request.get("data_access_level", "")).lower()
    integrations = [str(i).lower() for i in request.get("requested_integrations", [])]
    
    sensitive_data_classes = {
        "source_code", "production_telemetry", "production_access",
        "confidential_documents", "customer_pii", "employee_pii",
        "credentials_secrets"
    }
    has_sensitive_data = data_access in sensitive_data_classes
    has_prod_integration = any("production" in i or "cloud" in i or "git" in i or "repo" in i for i in integrations)
    vendor_sec_status = str(vendor_result.get("security_status", "")).lower()
    vendor_review_expired = vendor_result.get("review_expired", False)
    vendor_sec_unvetted = vendor_sec_status in ["not_completed", "pending", "unknown", "expired"]
    
    vendor_has_conflict = vendor_result.get("has_conflicting_evidence", False)
    
    if has_sensitive_data or has_prod_integration or vendor_review_expired or vendor_sec_unvetted or vendor_has_conflict:
        risk_flags.add("security_review_required")
        approvals.add("Security")
        if vendor_review_expired:
            risk_flags.add("vendor_review_expired")
        if vendor_has_conflict:
            risk_flags.add("conflicting_vendor_evidence")
        reasons = []
        if has_sensitive_data:
            reasons.append(f"sensitive data access ({data_access})")
        if has_prod_integration:
            reasons.append("production/repo integrations")
        if vendor_review_expired:
            reasons.append("expired security assessment (>365d)")
        if vendor_has_conflict:
            reasons.append("discrepancy between internal vendor registry and external risk service")
        if vendor_sec_unvetted:
            reasons.append(f"vendor security review status is '{vendor_sec_status}'")
        evidence_items.append(EvidenceItem(
            source="security_policy_gate",
            finding=f"Security review required due to: {', '.join(reasons)}.",
            reference="procurement_policy.md#5"
        ))

    # 8. Privacy Review Gate (Policy Section 6)
    has_pii = data_access in ["customer_pii", "employee_pii"] or vendor_result.get("processes_personal_data", False)
    stores_outside = vendor_result.get("stores_data_outside_region", False)
    
    if has_pii or stores_outside:
        risk_flags.add("privacy_review_required")
        approvals.add("Privacy")
        reasons = []
        if has_pii:
            reasons.append(f"personal data processing ({data_access})")
        if stores_outside:
            reasons.append("data stored outside operating region")
        evidence_items.append(EvidenceItem(
            source="privacy_policy_gate",
            finding=f"Privacy review required: {', '.join(reasons)}.",
            reference="procurement_policy.md#6"
        ))

    # 9. Legal Review Gate (Policy Section 7)
    proc_status = str(vendor_result.get("procurement_status", "New")).lower()
    is_new_vendor = proc_status in ["new", "unapproved", "unknown"]
    cost_val = float(annual_cost) if annual_cost is not None else 0.0
    terms_status = str(vendor_result.get("legal_terms_status", "Unknown")).lower()
    terms_not_approved = terms_status not in ["approved", "standard"]
    
    if (is_new_vendor and cost_val >= 10000.0) or terms_not_approved or stores_outside:
        risk_flags.add("legal_review_required")
        approvals.add("Legal")
        reasons = []
        if is_new_vendor and cost_val >= 10000.0:
            reasons.append(f"new vendor with annual spend >= $10k (${cost_val:,.2f})")
        if terms_not_approved:
            reasons.append(f"legal terms status is '{terms_status}'")
        if stores_outside:
            reasons.append("cross-region data processing")
        evidence_items.append(EvidenceItem(
            source="legal_policy_gate",
            finding=f"Legal review required: {', '.join(reasons)}.",
            reference="procurement_policy.md#7"
        ))

    # Ensure required approvals sorting and canonical role casing
    # Standard role taxonomy: Manager, Department Head, Procurement, Finance, CFO, Security, Privacy, Legal
    role_priority = [
        "Manager",
        "Department Head",
        "Procurement",
        "Finance",
        "CFO",
        "Security",
        "Privacy",
        "Legal"
    ]
    sorted_approvals = [role for role in role_priority if role in approvals]
    # Include any custom roles
    for role in sorted(approvals):
        if role not in sorted_approvals:
            sorted_approvals.append(role)

    return {
        "risk_flags": sorted(list(risk_flags)),
        "required_approvals": sorted_approvals,
        "missing_information": missing_info,
        "policy_evidence": evidence_items
    }
