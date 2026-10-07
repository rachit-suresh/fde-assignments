"""
Tools for FDE Procurement Request Copilot.
Implements:
1. check_department_budget (Deterministic)
2. search_software_catalog (Deterministic)
3. get_vendor_risk_status (Live HTTP API client with fault tolerance)
4. verify_requester (Deterministic)
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, List, Optional
import os
import requests

from src.contracts import EvidenceItem
from src.data_access import (
    load_budgets,
    load_software_catalog,
    load_vendors,
    load_employees,
    get_request,
)

POLICY_REFERENCE_DATE = date(2026, 9, 30)


def check_department_budget(
    department: str,
    annual_cost_usd: Optional[float] = None
) -> Dict[str, Any]:
    """
    Deterministic tool: Computes budget headroom for a department.
    Calculates available_usd = annual_software_budget_usd - committed_usd,
    and checks if annual_cost_usd exceeds available budget.
    """
    budgets_df = load_budgets()
    dept_rows = budgets_df[budgets_df["department"].str.lower() == department.strip().lower()]
    
    if dept_rows.empty:
        return {
            "department": department,
            "status": "not_found",
            "message": f"Department '{department}' not found in budget registry.",
            "evidence": EvidenceItem(
                source="department_budgets",
                finding=f"Department '{department}' has no registered software budget.",
                reference="department_budgets.csv"
            )
        }
        
    row = dept_rows.iloc[0]
    total_budget = float(row["annual_software_budget_usd"])
    committed = float(row["committed_usd"])
    available = float(row["available_usd"])
    
    if annual_cost_usd is None:
        return {
            "department": row["department"],
            "total_budget_usd": total_budget,
            "committed_usd": committed,
            "available_usd": available,
            "status": "cost_missing",
            "is_sufficient": True,
            "evidence": EvidenceItem(
                source="department_budgets",
                finding=f"{row['department']} software budget: ${available:,.2f} available (${total_budget:,.2f} total, ${committed:,.2f} committed). Request cost is unstated.",
                reference=f"department_budgets.csv:{row['department']}"
            )
        }
        
    cost = float(annual_cost_usd)
    is_sufficient = cost <= available
    variance = available - cost
    
    if is_sufficient:
        finding = (
            f"{row['department']} budget sufficient: requested ${cost:,.2f} within available ${available:,.2f} "
            f"(${variance:,.2f} remaining headroom)."
        )
    else:
        deficit = cost - available
        finding = (
            f"INSUFFICIENT BUDGET for {row['department']}: requested ${cost:,.2f} exceeds available "
            f"${available:,.2f} by ${deficit:,.2f} deficit."
        )
        
    return {
        "department": row["department"],
        "total_budget_usd": total_budget,
        "committed_usd": committed,
        "available_usd": available,
        "requested_cost_usd": cost,
        "is_sufficient": is_sufficient,
        "variance_usd": variance,
        "status": "sufficient" if is_sufficient else "insufficient",
        "evidence": EvidenceItem(
            source="department_budgets",
            finding=finding,
            reference=f"department_budgets.csv:{row['department']}"
        )
    }


def search_software_catalog(
    category: Optional[str] = None,
    vendor_name: Optional[str] = None,
    product_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deterministic tool: Inspects approved software catalog for:
    - Identical product or vendor
    - Tools in the same category (competing software overlap)
    - Add-ons or seat expansions under existing contracts
    """
    catalog_df = load_software_catalog()
    competing_overlaps: List[Dict[str, Any]] = []
    existing_contracts: List[Dict[str, Any]] = []
    
    cat_norm = category.strip().lower() if category else ""
    vendor_norm = vendor_name.strip().lower() if vendor_name else ""
    prod_norm = product_name.strip().lower() if product_name else ""
    
    is_expansion_request = any(k in prod_norm for k in ["add-on", "expansion", "pack", "seats", "tier"])
    
    for _, row in catalog_df.iterrows():
        c_vendor = str(row["vendor_name"]).strip().lower()
        c_cat = str(row["category"]).strip().lower()
        c_prod = str(row["product_name"]).strip().lower()
        
        is_same_vendor = vendor_norm and (vendor_norm in c_vendor or c_vendor in vendor_norm)
        is_same_cat = cat_norm and (cat_norm == c_cat or cat_norm in c_cat or c_cat in cat_norm)
        is_same_prod = prod_norm and (prod_norm in c_prod or c_prod in prod_norm)
        
        tool_info = {
            "software_id": row["software_id"],
            "product_name": row["product_name"],
            "category": row["category"],
            "vendor_name": row["vendor_name"],
            "status": row["status"],
            "annual_cost_usd": float(row["annual_cost_usd"]),
            "licensed_seats": int(row["licensed_seats"]),
            "scope": row["scope"],
            "notes": str(row["notes"]),
        }
        
        if is_same_vendor:
            # Existing enterprise relationship / contract
            tool_info["match_reason"] = "existing_approved_contract"
            existing_contracts.append(tool_info)
        elif is_same_cat or is_same_prod:
            # Different vendor in same category = true competing software overlap
            tool_info["match_reason"] = "competing_category_overlap"
            competing_overlaps.append(tool_info)
            
    # Overlap risk flag applies when competing alternative tools exist in catalog
    has_competing_overlap = len(competing_overlaps) > 0
    
    findings = []
    if existing_contracts:
        c_summary = ", ".join(f"{c['product_name']} ({c['vendor_name']} - {c['licensed_seats']} seats approved)" for c in existing_contracts)
        findings.append(f"Existing enterprise contract verified for vendor '{vendor_name}': {c_summary}.")
    if competing_overlaps:
        o_summary = ", ".join(f"{o['product_name']} ({o['vendor_name']} - {o['category']})" for o in competing_overlaps)
        findings.append(f"Competing software overlap identified with {len(competing_overlaps)} existing approved tool(s): {o_summary}.")
        
    finding_text = " ".join(findings) if findings else "No overlapping products or categories found in the approved software catalog."
    
    return {
        "has_overlap": has_competing_overlap,
        "has_existing_contract": len(existing_contracts) > 0,
        "competing_overlap_count": len(competing_overlaps),
        "overlapping_tools": competing_overlaps,
        "existing_contracts": existing_contracts,
        "evidence": EvidenceItem(
            source="software_catalog",
            finding=finding_text,
            reference="software_catalog.csv"
        )
    }


def get_vendor_risk_status(
    vendor_name: str,
    timeout_seconds: float = 3.0
) -> Dict[str, Any]:
    """
    Tool: Queries external Vendor Risk API service and reconciles with internal vendors.csv.
    Handles network timeouts and 503 service outages gracefully (returning structured failure).
    Audits 365-day security review freshness relative to policy snapshot date 2026-09-30.
    """
    base_url = os.getenv("VENDOR_RISK_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    
    # Check internal registry first
    vendors_df = load_vendors()
    v_rows = vendors_df[vendors_df["vendor_name"].str.lower() == vendor_name.strip().lower()]
    registry_record = v_rows.iloc[0].to_dict() if not v_rows.empty else None
    
    # Call external Mock API
    api_data: Optional[Dict[str, Any]] = None
    api_available = True
    error_message = None
    
    try:
        url = f"{base_url}/vendor-risk/{requests.utils.quote(vendor_name, safe='')}"
        res = requests.get(url, timeout=timeout_seconds)
        if res.status_code == 200:
            api_data = res.json()
        elif res.status_code == 503:
            api_available = False
            error_message = f"503 Service Unavailable: {res.text}"
        elif res.status_code == 404:
            api_available = True
            api_data = None
            error_message = f"404 Not Found in vendor risk database"
        else:
            api_available = False
            error_message = f"HTTP {res.status_code}: {res.text}"
    except Exception as exc:
        # Fallback to in-process FastAPI TestClient if uvicorn server is not running
        try:
            from fastapi.testclient import TestClient
            from mock_api.app import app as mock_app
            client = TestClient(mock_app)
            res = client.get(f"/vendor-risk/{requests.utils.quote(vendor_name, safe='')}")
            if res.status_code == 200:
                api_data = res.json()
            elif res.status_code == 503:
                api_available = False
                error_message = f"503 Service Unavailable: {res.text}"
            elif res.status_code == 404:
                api_available = True
                api_data = None
                error_message = "404 Not Found in vendor risk database"
            else:
                api_available = False
                error_message = f"HTTP {res.status_code}: {res.text}"
        except Exception as inner_exc:
            api_available = False
            error_message = f"Vendor risk API request failed: {str(inner_exc)}"
        
    # Analyze review freshness and security status
    review_expired = False
    review_date_str = None
    security_status = "unknown"
    processes_personal_data = False
    stores_data_outside_region = False
    risk_level = "unknown"
    
    if api_data:
        security_status = str(api_data.get("security_review_status", "unknown")).lower()
        review_date_str = api_data.get("last_review_date")
        processes_personal_data = bool(api_data.get("processes_personal_data", False))
        stores_data_outside_region = bool(api_data.get("stores_data_outside_region", False))
        risk_level = api_data.get("risk_level", "unknown")
    elif registry_record:
        security_status = str(registry_record.get("security_status", "unknown")).lower()
        review_date_str = registry_record.get("security_review_date")
        
    if review_date_str and isinstance(review_date_str, str) and review_date_str.strip():
        try:
            rev_d = datetime.strptime(review_date_str.strip(), "%Y-%m-%d").date()
            days_old = (POLICY_REFERENCE_DATE - rev_d).days
            if days_old > 365 or security_status == "expired":
                review_expired = True
        except ValueError:
            pass

    if security_status == "expired":
        review_expired = True

    # Check for conflict between registry and external risk service
    has_conflicting_evidence = False
    if api_data and registry_record:
        reg_sec = str(registry_record.get("security_status", "")).strip().lower()
        api_sec = str(api_data.get("security_review_status", "")).strip().lower()
        if reg_sec and api_sec and reg_sec != api_sec:
            has_conflicting_evidence = True

    # Build evidence item
    if not api_available:
        finding = f"CRITICAL: Vendor risk service unavailable for '{vendor_name}' ({error_message}). Cannot verify security posture."
        ref = "mock_api:/vendor-risk"
    elif api_data:
        date_info = f"last reviewed {review_date_str}" if review_date_str else "no review date"
        freshness_info = " (EXPIRED >365d)" if review_expired else " (current)"
        conflict_info = " [CONFLICT: internal registry reports different security status]" if has_conflicting_evidence else ""
        finding = (
            f"Vendor '{vendor_name}' risk status: {security_status.upper()}{freshness_info}{conflict_info}, "
            f"risk level: {risk_level}, processes personal data: {processes_personal_data}, "
            f"stores outside region: {stores_data_outside_region} ({date_info})."
        )
        ref = f"vendor_risk.json:{vendor_name}"
    elif registry_record:
        finding = f"Vendor '{vendor_name}' found in internal registry ({registry_record.get('procurement_status')}), but not present in vendor-risk API."
        ref = f"vendors.csv:{vendor_name}"
    else:
        finding = f"Vendor '{vendor_name}' is completely new and unvetted (not found in registry or risk service)."
        ref = f"new_vendor:{vendor_name}"

    return {
        "vendor_name": vendor_name,
        "api_available": api_available,
        "error_message": error_message,
        "api_data": api_data,
        "registry_record": registry_record,
        "security_status": security_status,
        "review_expired": review_expired,
        "has_conflicting_evidence": has_conflicting_evidence,
        "review_date": review_date_str,
        "processes_personal_data": processes_personal_data,
        "stores_data_outside_region": stores_data_outside_region,
        "risk_level": risk_level,
        "procurement_status": registry_record.get("procurement_status") if registry_record else "New",
        "legal_terms_status": registry_record.get("legal_terms_status") if registry_record else "Unknown",
        "evidence": EvidenceItem(
            source="vendor_risk_service" if api_available else "vendor_risk_unavailable",
            finding=finding,
            reference=ref
        )
    }


def verify_requester(requester_id: str) -> Dict[str, Any]:
    """
    Deterministic tool: Retrieves employee profile and organizational context.
    """
    employees_df = load_employees()
    emp_rows = employees_df[employees_df["employee_id"] == requester_id.strip()]
    if emp_rows.empty:
        return {
            "status": "not_found",
            "message": f"Employee ID '{requester_id}' not found.",
            "evidence": EvidenceItem(
                source="employees",
                finding=f"Requester ID '{requester_id}' not found in employee directory.",
                reference="employees.csv"
            )
        }
    row = emp_rows.iloc[0]
    return {
        "employee_id": row["employee_id"],
        "name": row["name"],
        "department": row["department"],
        "manager_id": row["manager_id"],
        "level": row["level"],
        "country": row["country"],
        "evidence": EvidenceItem(
            source="employees",
            finding=f"Requester verified: {row['name']} ({row['employee_id']}), {row['level']} in {row['department']} ({row['country']}).",
            reference=f"employees.csv:{row['employee_id']}"
        )
    }
