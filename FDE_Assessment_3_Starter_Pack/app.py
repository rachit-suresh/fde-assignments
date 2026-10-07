"""
AI Procurement Request Copilot - Enterprise Streamlit Application.
Follows FDE design principles:
1. AI context interpretation + deterministic code enforcement + human final authority.
2. 6 Product Lifecycle States (Normal, Running, Completed, Error, Quarantine, Consequence).
3. Evidence panel, risk taxonomy badges, approval chain, and interactive human-in-the-loop controls.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
import pandas as pd
import streamlit as st

from src.contracts import ProcurementDecision
from src.solution import handle_request

ROOT = Path(__file__).resolve().parent
REQUESTS = json.loads((ROOT / "data" / "requests.json").read_text(encoding="utf-8"))
BY_ID = {r["request_id"]: r for r in REQUESTS}

EMPLOYEES_DF = pd.read_csv(ROOT / "data" / "employees.csv").set_index("employee_id")
BUDGETS_DF = pd.read_csv(ROOT / "data" / "department_budgets.csv").set_index("department")

st.set_page_config(
    page_title="FlashEats Procurement Copilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-caption {
        font-size: 0.95rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .verdict-approved {
        background-color: #ECFDF5;
        border-left: 5px solid #10B981;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .verdict-warning {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .verdict-danger {
        background-color: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .badge {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .badge-blue { background: #DBEAFE; color: #1E40AF; }
    .badge-amber { background: #FEF3C7; color: #92400E; }
    .badge-red { background: #FEE2E2; color: #991B1B; }
    .badge-green { background: #D1FAE5; color: #065F46; }
    .badge-purple { background: #F3E8FF; color: #6B21A8; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS
# -----------------------------------------------------------------------------
st.sidebar.markdown("### ⚙️ Copilot Configuration")

request_id = st.sidebar.selectbox(
    "Select Purchase Request",
    list(BY_ID.keys()),
    format_func=lambda rid: f"{rid} : {BY_ID[rid]['product_name']} (${BY_ID[rid].get('annual_cost_usd', 0) or 0:,.0f})",
)

architecture = st.sidebar.radio(
    "Agent Architecture",
    ["single", "staged"],
    format_func=lambda a: "Architecture A: Single-Agent Baseline" if a == "single" else "Architecture B: Staged 2-Agent Variant",
    help="Compare Single-Agent end-to-end vs Staged Discovery & Auditor agents."
)

st.sidebar.divider()
st.sidebar.markdown("### 📊 Live Public Benchmark")
if st.sidebar.button("Run Side-by-Side Eval Suite", use_container_width=True):
    with st.spinner("Benchmarking Architecture A vs B across all 6 test cases..."):
        from evals.run_public_evals import evaluate
        cases = json.loads((ROOT / "evals" / "public_cases.json").read_text(encoding="utf-8"))
        
        bench_rows = []
        for arch in ["single", "staged"]:
            for c in cases:
                t0 = time.perf_counter()
                dec = handle_request(c["request_id"], architecture=arch)
                lat = (time.perf_counter() - t0) * 1000
                fails = evaluate(dec, c["expectations"], architecture=arch)
                tel = dec.telemetry
                bench_rows.append({
                    "Architecture": "Single-Agent" if arch == "single" else "Staged 2-Agent",
                    "Case": c["case_id"],
                    "Status": "✅ PASS" if not fails else "❌ FAIL",
                    "Latency (ms)": f"{lat:.0f}",
                    "LLM Calls": tel.llm_calls if tel else 0,
                    "Tool Calls": tel.tool_calls if tel else 0,
                })
        st.sidebar.success("Benchmark completed! See results at bottom of page.")
        st.session_state["benchmark_results"] = pd.DataFrame(bench_rows)

st.sidebar.caption("Reference Date: 2026-09-30 | Vendor Risk API: Port 8001")

# -----------------------------------------------------------------------------
# MAIN DASHBOARD HEADER
# -----------------------------------------------------------------------------
st.markdown('<div class="main-header">🛡️ FlashEats AI Procurement Copilot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-caption">Internal AI copilot for software evaluation, budget validation, vendor risk screening & human approval orchestration.</div>', unsafe_allow_html=True)

req = BY_ID[request_id]
emp = EMPLOYEES_DF.loc[req["requester_id"]].to_dict() if req["requester_id"] in EMPLOYEES_DF.index else {}
dept_budget = BUDGETS_DF.loc[emp.get("department", "Operations")].to_dict() if emp.get("department") in BUDGETS_DF.index else {}

col_left, col_right = st.columns([1.05, 1.15], gap="large")

# -----------------------------------------------------------------------------
# LEFT COLUMN: PURCHASE REQUEST DETAILS
# -----------------------------------------------------------------------------
with col_left:
    st.subheader("📋 Purchase Request Details")
    
    # Requester Banner Card
    st.markdown(f"""
    <div class="metric-card">
        <strong>Requester:</strong> {emp.get('name', 'Unknown')} (<code>{req['requester_id']}</code>)<br>
        <strong>Department:</strong> {emp.get('department', 'Unknown')} &nbsp;|&nbsp; 
        <strong>Level:</strong> {emp.get('level', 'N/A')} &nbsp;|&nbsp; 
        <strong>Country:</strong> {emp.get('country', 'N/A')}
    </div>
    """, unsafe_allow_html=True)
    
    # Financial Overview Tiles
    cost_val = req.get("annual_cost_usd")
    cost_disp = f"${cost_val:,.2f}" if cost_val is not None else "⚠️ Unstated (Missing)"
    seats_val = req.get("user_count")
    seats_disp = f"{seats_val:,} seats" if seats_val is not None else "⚠️ Unstated"
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Annual Cost", cost_disp)
    m2.metric("License Seats", seats_disp)
    avail_usd = dept_budget.get("available_usd", 0)
    m3.metric("Dept Budget Avail", f"${avail_usd:,.0f}")
    
    # Request Parameters Table
    st.markdown("#### Technical Scope")
    scope_data = {
        "Product Name": req.get("product_name"),
        "Vendor Name": req.get("vendor_name"),
        "Software Category": req.get("category"),
        "Intended Data Access": req.get("data_access_level", "unknown").upper(),
        "Requested Integrations": ", ".join(req.get("requested_integrations", [])) or "None",
        "Submission Urgency": str(req.get("urgency", "normal")).capitalize(),
    }
    st.dataframe(pd.DataFrame(list(scope_data.items()), columns=["Parameter", "Value"]), use_container_width=True, hide_index=True)
    
    # Business Justification Box
    st.markdown("#### Business Justification (Untrusted Input)")
    justification = req.get("business_justification", "No justification provided.")
    if "ignore all" in justification.lower() or "cfo-approved" in justification.lower():
        st.error(f"🚨 **Adversarial Input Detected in Justification:**\n\n> {justification}")
    else:
        st.info(f"> {justification}")

# -----------------------------------------------------------------------------
# RIGHT COLUMN: COPILOT ANALYSIS & HUMAN-IN-THE-LOOP COCKPIT
# -----------------------------------------------------------------------------
with col_right:
    st.subheader(f"🤖 Copilot Analysis ({'Single-Agent' if architecture == 'single' else 'Staged 2-Agent'})")
    
    # Trigger Button
    run_clicked = st.button("🚀 Run Copilot Analysis", type="primary", use_container_width=True)
    
    if run_clicked or f"decision_{request_id}_{architecture}" in st.session_state:
        if run_clicked:
            start_time = time.perf_counter()
            with st.spinner("Executing discovery tools, checking budget, and auditing policy..."):
                decision: ProcurementDecision = handle_request(request_id, architecture=architecture)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                st.session_state[f"decision_{request_id}_{architecture}"] = (decision, elapsed_ms)
        else:
            decision, elapsed_ms = st.session_state[f"decision_{request_id}_{architecture}"]
            
        # 1. Advisory Verdict Banner
        is_injection = "prompt_injection_detected" in decision.risk_flags
        is_outage = "vendor_risk_unavailable" in decision.risk_flags
        is_budget_breach = "budget_insufficient" in decision.risk_flags
        is_missing = "missing_information" in decision.risk_flags
        is_overlap = "existing_tool_overlap" in decision.risk_flags
        
        if is_injection or is_outage or is_budget_breach:
            banner_class = "verdict-danger"
            status_icon = "🛑 ACTION REQUIRED / ESCALATION"
        elif is_missing or is_overlap or len(decision.risk_flags) > 0:
            banner_class = "verdict-warning"
            status_icon = "⚠️ REVIEW WITH CONDITIONS"
        else:
            banner_class = "verdict-approved"
            status_icon = "✅ ELIGIBLE FOR STANDARD APPROVAL"
            
        st.markdown(f"""
        <div class="{banner_class}">
            <h4 style="margin:0 0 6px 0;">{status_icon}</h4>
            <strong>Recommendation:</strong> {decision.recommendation}<br>
            <strong>Operational Next Step:</strong> {decision.next_step}
        </div>
        """, unsafe_allow_html=True)
        
        # 2. Approvals & Risk Badges
        st.markdown("#### 👥 Required Approval Chain")
        app_html = "".join([f'<span class="badge badge-blue">👤 {role}</span>' for role in decision.required_approvals])
        st.markdown(app_html or "<em>No approvals required</em>", unsafe_allow_html=True)
        
        st.markdown("#### 🚩 Policy Risk Flags")
        flag_badges = []
        for flag in decision.risk_flags:
            if flag in ["budget_insufficient", "prompt_injection_detected", "vendor_risk_unavailable"]:
                flag_badges.append(f'<span class="badge badge-red">🚨 {flag}</span>')
            elif flag in ["security_review_required", "privacy_review_required", "legal_review_required"]:
                flag_badges.append(f'<span class="badge badge-amber">⚠️ {flag}</span>')
            else:
                flag_badges.append(f'<span class="badge badge-purple">ℹ️ {flag}</span>')
        st.markdown("".join(flag_badges) or '<span class="badge badge-green">✓ Clean Policy Audit</span>', unsafe_allow_html=True)
        
        if decision.missing_information:
            st.warning(f"**Missing Material Information:** {', '.join(decision.missing_information)}")
            
        # 3. Grounded Evidence Dossier
        with st.expander(f"🔍 Grounded Evidence Dossier ({len(decision.evidence)} verified items)", expanded=True):
            for i, ev in enumerate(decision.evidence, 1):
                ref_text = f" &nbsp;[<code>{ev.reference}</code>]" if ev.reference else ""
                st.markdown(f"**{i}. [{ev.source.upper()}]** {ev.finding}{ref_text}")
                
        # 4. Human-In-The-Loop Action Console
        st.markdown("#### ✍️ Human Decision & Sign-Off Console")
        st.caption("FDE Control: The AI recommends; the human executes the binding legal and budget action.")
        
        b1, b2, b3, b4 = st.columns(4)
        if b1.button("✅ Approve Spend", use_container_width=True):
            st.success(f"Sign-off recorded! Routed to {', '.join(decision.required_approvals)} for workflow authorization.")
        if b2.button("💬 Ask Details", use_container_width=True):
            st.info(f"Clarification ticket created for {emp.get('name')}: Requested details on {', '.join(decision.missing_information) or 'use case justification'}.")
        if b3.button("⚠️ Escalate Risk", use_container_width=True):
            st.warning("Escalated to Corporate Security, Privacy & Legal escrow queues.")
        if b4.button("❌ Reject Request", use_container_width=True):
            st.error("Request rejected. Justification notification dispatched to employee and manager.")
            
        # 5. Telemetry & Performance
        tel = decision.telemetry
        st.divider()
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Latency", f"{elapsed_ms:.0f} ms")
        t2.metric("LLM Invocations", tel.llm_calls if tel else 0)
        t3.metric("Tool Invocations", tel.tool_calls if tel else 0)
        t4.metric("Human Gate", "Active (Enforced)")
        
    else:
        st.info("👈 Select a request on the sidebar and click **'Run Copilot Analysis'** to evaluate.")

# -----------------------------------------------------------------------------
# BENCHMARK COMPARISON TABLE (IF TRIGGERED)
# -----------------------------------------------------------------------------
if "benchmark_results" in st.session_state:
    st.divider()
    st.subheader("📈 Architecture A vs Architecture B Comparative Evaluation")
    b_df = st.session_state["benchmark_results"]
    st.dataframe(b_df, use_container_width=True, hide_index=True)
