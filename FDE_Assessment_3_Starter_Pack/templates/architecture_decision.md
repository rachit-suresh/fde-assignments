# Architecture Decision Memo: AI Procurement Request Copilot

**Maximum length: 500 words** | **Word count: 419 words**

## Decision
We recommend shipping **Architecture A (Single-Agent Baseline)** for production MVP deployment today.

## Evidence
Both architectures were evaluated against the exact same 6 public benchmark scenarios spanning low-value approvals, catalog overlaps, sensitive source-code integrations, budget deficits, adversarial prompt injections, and upstream API outages.

| Metric | Single-Agent (Architecture A) | Staged 2-Agent (Architecture B) |
|---|---:|---:|
| **Benchmark Pass Rate** | **6 / 6 (100%)** | **6 / 6 (100%)** |
| **Average End-to-End Latency** | **3,239 ms** | **11,363 ms (sequential)** |
| **LLM Invocations per Request** | **1 call** | **2 calls** |
| **Deterministic Tool Calls** | **4 calls** | **4 calls** |
| **Notable Policy / Grounding Failures** | **0** | **0** |
| **Prompt Injection Containment** | **100% (Isolated)** | **100% (Isolated)** |
| **API Outage Degradation (PUB-06)** | **Graceful 503 Escrow** | **Graceful 503 Escrow** |

## Trade-offs
* **Architecture A (Single-Agent Baseline):** Delivers ~3.2s end-to-end response times with half the LLM token footprint and API cost. By pairing a unified agent with deterministic policy gates (budget arithmetic, dollar threshold matrix, 365-day expiry calculations), it achieves 100% compliance without orchestration complexity.
* **Architecture B (Staged 2-Agent Variant):** Decomposes the task cleanly into a Discovery Analyst and a Compliance Auditor. While architecturally modular, it doubles token consumption, increases invocation latency by 3.5x (~11.4s), introduces an intermediate dossier serialization contract, and increases rate-limit exposure—without yielding any increase in benchmark accuracy or policy adherence.

## Risks & Limitations
Before scaling beyond the pilot phase, we must validate:
1. **Dynamic Policy Updates:** Currently, threshold matrices and reference dates (`2026-09-30`) reside in Python configuration. Enterprise deployment will require an admin policy management interface with live hot-reloading.
2. **Catalog Fuzzy Matching Thresholds:** Production semantic search should integrate embeddings-based vector retrieval for multi-lingual and edge-case tool descriptions.
3. **Upstream Rate Limiting:** While our client handles HTTP 503 outages gracefully, long-duration API outages will require asynchronous background retries and webhook notifications.

## Why This is the Right MVP
The core Forward Deployed Engineering (FDE) principle is: *"A simpler system that performs as well or better is a stronger answer than unnecessary orchestration."*

Because deterministic Python code handles mathematical boundaries, spend thresholds, and date audits, the LLM is leveraged exclusively for context interpretation, semantic overlap discovery, and executive recommendation synthesis. Architecture A provides maximum reliability, lowest latency, zero framework bloat, and minimal operating cost, while strictly preserving human authority over final purchasing decisions.
