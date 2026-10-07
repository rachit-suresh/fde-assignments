"""
Comprehensive Edge-Case Audit across all 10 requests in data/requests.json.
Validates:
- Approvals chain
- Risk flags
- Evidence items
- LLM response synthesis
- Pacing and rate limits
"""
import json
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.solution import handle_request
requests = json.loads((ROOT / "data" / "requests.json").read_text(encoding="utf-8"))

print(f"Total Requests in Dataset: {len(requests)}\n")

for r in requests:
    rid = r["request_id"]
    t0 = time.perf_counter()
    dec = handle_request(rid, architecture="single")
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"[{rid}] {r['product_name']} (${r.get('annual_cost_usd') or 0}) - {elapsed:.0f} ms")
    print(f"   Approvals:   {dec.required_approvals}")
    print(f"   Risk Flags:  {dec.risk_flags}")
    print(f"   Missing:     {dec.missing_information}")
    print(f"   Rec:         {dec.recommendation[:90]}...")
    print(f"   Next Step:   {dec.next_step[:90]}...")
    print(f"   Evidence:    {len(dec.evidence)} items | Telemetry: LLM={dec.telemetry.llm_calls}, Tools={dec.telemetry.tool_calls}")
    print()
    time.sleep(1.2)  # rate pacing
