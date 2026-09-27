"""
Pipeline Configuration & Business Constants
"""
import os
from pathlib import Path

def resolve_pack_root() -> Path:
    """
    Locates the FlashEats data pack directory by checking common relative paths.
    """
    current = Path(__file__).resolve().parent
    candidates = [
        current.parent.parent / "flasheats-classroom-pack",
        current.parent / "flasheats-classroom-pack",
        Path.cwd() / "flasheats-classroom-pack",
        Path.cwd().parent / "flasheats-classroom-pack"
    ]
    for c in candidates:
        if (c / "database" / "flasheats.db").exists():
            return c.resolve()
            
    # Fallback search upwards
    for parent in current.parents:
        cand = parent / "flasheats-classroom-pack"
        if (cand / "database" / "flasheats.db").exists():
            return cand.resolve()
            
    raise FileNotFoundError("Could not locate flasheats-classroom-pack with database/flasheats.db")

PACK_ROOT = resolve_pack_root()
DB_PATH = PACK_ROOT / "database" / "flasheats.db"
DATA_DIR = PACK_ROOT / "data"

ASSIGNMENT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ASSIGNMENT_ROOT / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Business Rule Constants
LATE_THRESHOLD_MIN = 0.0          # Delay > 0 min is considered late per SLA
SEVERE_LATE_THRESHOLD_MIN = 10.0  # Delay > 10 min is severe late
MAX_PHYSICAL_DELAY_MIN = 180.0    # Outlier threshold for data sanity

# Required target columns for canonical workflow mart
CANONICAL_MART_COLS = [
    "order_id",
    "customer_id",
    "support_opened",
    "cancel_attempted",
    "intervention_count",
    "intervention_types",
    "final_status",
    "late_flag",
    "delay_min"
]
