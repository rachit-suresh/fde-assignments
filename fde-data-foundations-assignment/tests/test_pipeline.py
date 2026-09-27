"""
Automated Test Suite for FlashEats FDE Data Pipeline (Class 8 Dependability)
Verifies multi-modal ingestion, data validation gates, workflow mart grain integrity,
and mathematical consistency of KPI metrics.
"""
import sys
import unittest
import pandas as pd
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.config import OUTPUTS_DIR, CANONICAL_MART_COLS
from pipeline.ingest import ingest_raw_sources
from pipeline.validate import validate_and_clean_sources
from pipeline.transform import build_order_workflow_mart
from pipeline.metrics import calculate_kpi_metrics

class TestFlashEatsPipeline(unittest.TestCase):
    """Integration and unit tests for the dependable data pipeline."""

    @classmethod
    def setUpClass(cls):
        """Runs the pipeline stages once to provide shared test fixtures."""
        cls.raw_tables, cls.ingest_meta = ingest_raw_sources()
        cls.clean_tables, cls.val_report = validate_and_clean_sources(cls.raw_tables)
        cls.full_mart, cls.canonical_mart = build_order_workflow_mart(cls.clean_tables)
        cls.scorecard_df, cls.diagnostics = calculate_kpi_metrics(cls.full_mart)

    def test_01_ingestion_completeness(self):
        """Verify all essential transactional and telemetry tables are extracted."""
        expected_tables = [
            "orders", "customers", "restaurants", "drivers",
            "customer_app_actions", "support_tickets",
            "order_interventions", "order_outcomes"
        ]
        for tbl in expected_tables:
            self.assertIn(tbl, self.raw_tables, f"Missing table in raw ingestion: {tbl}")
            self.assertGreater(len(self.raw_tables[tbl]), 0, f"Table {tbl} is unexpectedly empty")

    def test_02_validation_deduplication(self):
        """Verify Gate 1 eliminates duplicate order rows without silent mutation."""
        clean_orders = self.clean_tables["orders"]
        total_rows = len(clean_orders)
        unique_orders = clean_orders["order_id"].nunique()
        self.assertEqual(total_rows, unique_orders, "Clean orders table contains unhandled duplicate PKs")
        self.assertEqual(unique_orders, 1600, "Clean orders count should strictly equal 1,600 unique orders")

    def test_03_validation_report_integrity(self):
        """Verify all 6 validation gates were evaluated and logged, capturing known client data anomalies."""
        self.assertEqual(self.val_report["rules_evaluated"], 6)
        self.assertEqual(self.val_report["status"], "PASS")
        self.assertTrue(self.val_report["gates"]["gate_1_pk_uniqueness"]["passed"])
        # Gate 2 accurately profiles the 5 known client temporal inversions (delivery < pickup)
        self.assertEqual(self.val_report["gates"]["gate_2_temporal_monotonicity"]["anomalies_detected"], 1)
        self.assertIn("5 orders have delivery_at earlier than pickup_at", 
                      self.val_report["gates"]["gate_2_temporal_monotonicity"]["details"][0])
        self.assertTrue(self.val_report["gates"]["gate_3_domain_normalization"]["passed"])
        self.assertTrue(self.val_report["gates"]["gate_5_sla_delay_consistency"]["passed"])

    def test_04_canonical_mart_grain_and_schema(self):
        """Verify the canonical workflow mart has exact shape (1600, 9) and correct schema."""
        self.assertEqual(self.canonical_mart.shape, (1600, 9))
        self.assertListEqual(list(self.canonical_mart.columns), CANONICAL_MART_COLS)
        self.assertEqual(self.canonical_mart["order_id"].nunique(), 1600)
        self.assertEqual(self.canonical_mart["order_id"].isna().sum(), 0)

    def test_05_kpi_metrics_scorecard_validity(self):
        """Verify the 5 required KPI metrics are computed with expected categories and ranges."""
        self.assertEqual(len(self.scorecard_df), 5)
        categories = set(self.scorecard_df["Category"])
        self.assertIn("Outcome", categories, "Missing required Outcome metric")
        self.assertIn("Interaction", categories, "Missing required Interaction metric")
        self.assertIn("Intervention", categories, "Missing required Intervention metric")

        # Check severe late rate calculation
        severe_row = self.scorecard_df[self.scorecard_df["Metric Name"].str.contains("Severe Late")].iloc[0]
        self.assertIn("22.78%", severe_row["Observed Value"])

        # Check anxiety velocity
        anxiety_row = self.scorecard_df[self.scorecard_df["Metric Name"].str.contains("Anxiety")].iloc[0]
        self.assertIn("1.39", anxiety_row["Observed Value"])

    def test_06_disk_artifacts_exist(self):
        """Verify all required deliverables exist on disk in outputs/."""
        required_artifacts = [
            OUTPUTS_DIR / "pipeline_execution.log",
            OUTPUTS_DIR / "validation_report.json",
            OUTPUTS_DIR / "order_workflow_mart.csv",
            OUTPUTS_DIR / "kpi_metrics_scorecard.csv"
        ]
        for path in required_artifacts:
            self.assertTrue(path.exists(), f"Missing required pipeline artifact: {path}")
            self.assertGreater(path.stat().st_size, 0, f"Artifact {path} is empty")

if __name__ == "__main__":
    unittest.main(verbosity=2)
