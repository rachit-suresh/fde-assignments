"""
Master Pipeline Orchestrator (Class 8 Dependable Pipeline)
Executes the end-to-end repeatable workflow:
  Ingest -> Validate -> Transform -> Metrics Output
Supports automated logging, error handling, idempotent rerun behavior, and CLI execution.
"""
import sys
import json
import logging
import argparse
from pathlib import Path

# Add project root to sys.path so modules import seamlessly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import OUTPUTS_DIR
from pipeline.ingest import ingest_raw_sources
from pipeline.validate import validate_and_clean_sources
from pipeline.transform import build_order_workflow_mart
from pipeline.metrics import calculate_kpi_metrics

def setup_logging(log_file: Path) -> logging.Logger:
    """Configures multi-handler logging to file and console."""
    logger = logging.getLogger("FlashEatsPipeline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # File Handler
    fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

    return logger

def run_pipeline(output_dir: Path = OUTPUTS_DIR, strict: bool = False) -> int:
    """
    Runs the complete data foundations pipeline.
    
    Args:
        output_dir: Path where artifacts and logs will be written.
        strict: If True, halts execution if data quality anomalies are detected.
        
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "pipeline_execution.log"
    logger = setup_logging(log_path)

    logger.info("=" * 80)
    logger.info("STARTING FLASHEATS FDE DATA FOUNDATIONS PIPELINE")
    logger.info("Output Directory: %s", output_dir)
    logger.info("=" * 80)

    try:
        # Step 1: Ingest
        logger.info("STAGE 1: MULTI-MODAL INGESTION")
        raw_tables, ingest_meta = ingest_raw_sources()
        logger.info("Stage 1 Successful: Ingested %d tables", len(raw_tables))

        # Step 2: Validate
        logger.info("STAGE 2: BUSINESS-ORIENTED DATA VALIDATION")
        clean_tables, val_report = validate_and_clean_sources(raw_tables)
        val_path = output_dir / "validation_report.json"
        with open(val_path, "w", encoding="utf-8") as f:
            json.dump(val_report, f, indent=2, default=str)
        logger.info("Stage 2 Successful: Validation report written to %s", val_path)

        if strict and len(val_report["anomalies"]) > 0:
            logger.error("Strict mode enabled: Halting due to %d profiled anomalies", len(val_report["anomalies"]))
            return 1

        # Step 3: Transform
        logger.info("STAGE 3: CANONICAL WORKFLOW MODELING")
        full_mart, canonical_mart = build_order_workflow_mart(clean_tables)
        mart_path = output_dir / "order_workflow_mart.csv"
        canonical_mart.to_csv(mart_path, index=False)
        logger.info("Stage 3 Successful: Canonical mart written to %s (Shape: %s)", mart_path, str(canonical_mart.shape))

        # Step 4: Metrics
        logger.info("STAGE 4: BUSINESS KPI METRICS GENERATION")
        scorecard_df, diagnostics = calculate_kpi_metrics(full_mart)
        scorecard_path = output_dir / "kpi_metrics_scorecard.csv"
        scorecard_df.to_csv(scorecard_path, index=False)
        logger.info("Stage 4 Successful: Scorecard written to %s", scorecard_path)

        logger.info("=" * 80)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY (ALL 4 STAGES PASSED)")
        logger.info("Executive KPI Scorecard Summary:")
        for _, row in scorecard_df.iterrows():
            logger.info("  * %-35s : %s", row["Metric Name"], row["Observed Value"])
        logger.info("=" * 80)
        return 0

    except Exception as e:
        logger.exception("CRITICAL PIPELINE EXECUTION FAILURE: %s", str(e))
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FlashEats FDE Data Pipeline")
    parser.add_argument("--output-dir", type=Path, default=OUTPUTS_DIR, help="Destination directory for outputs")
    parser.add_argument("--strict", action="store_true", help="Fail pipeline if any validation anomaly is detected")
    parser.add_argument("--rerun", action="store_true", help="Idempotent rerun flag")
    args = parser.parse_args()

    sys.exit(run_pipeline(output_dir=args.output_dir, strict=args.strict))
