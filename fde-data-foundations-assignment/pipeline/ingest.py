"""
Multi-Modal Ingestion Module (Class 5 Retrieval)
Handles parameterized SQL queries and file-based ingestion while guaranteeing
completeness audits and preserving raw inputs untouched.
"""
import sqlite3
import json
import logging
from typing import Dict, Any, Tuple
import pandas as pd
from pipeline.config import DB_PATH, DATA_DIR

logger = logging.getLogger("FlashEatsPipeline.Ingest")

def ingest_raw_sources() -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
    """
    Ingests all raw sources across two primary retrieval modes:
    1. Relational Mode: SQLite database queries for transactional tables.
    2. File Mode: CSV and JSON for event telemetry, support tickets, and interventions.
    
    Returns:
        raw_tables: Dictionary of raw DataFrames.
        ingestion_metadata: Audit metadata tracking row counts and completeness.
    """
    logger.info("Initiating multi-modal data ingestion from %s and %s", DB_PATH, DATA_DIR)
    raw_tables: Dict[str, pd.DataFrame] = {}
    ingestion_metadata: Dict[str, Any] = {}

    # Mode 1: Relational SQL Extraction
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database file not found at {DB_PATH}")
        
    con = sqlite3.connect(DB_PATH)
    try:
        sql_tables = ["orders", "customers", "restaurants", "drivers"]
        for tbl in sql_tables:
            query = f"SELECT * FROM {tbl}"
            df = pd.read_sql_query(query, con)
            raw_tables[tbl] = df
            ingestion_metadata[tbl] = {
                "source_type": "sqlite_database",
                "source_path": str(DB_PATH),
                "row_count": len(df),
                "col_count": len(df.columns),
                "columns": list(df.columns)
            }
            logger.info("Extracted SQL table '%s': %d rows, %d columns", tbl, len(df), len(df.columns))
    finally:
        con.close()

    # Mode 2: File Ingestion (CSV / JSON)
    csv_sources = {
        "customer_app_actions": DATA_DIR / "customer_app_actions.csv",
        "support_tickets": DATA_DIR / "support_tickets.csv",
        "order_interventions": DATA_DIR / "order_interventions.csv",
        "order_outcomes": DATA_DIR / "order_outcomes.csv"
    }

    # Optional auxiliary sources if present
    if (DATA_DIR / "restaurant_status.csv").exists():
        csv_sources["restaurant_status"] = DATA_DIR / "restaurant_status.csv"

    for name, path in csv_sources.items():
        if not path.exists():
            raise FileNotFoundError(f"Required CSV source missing: {path}")
        df = pd.read_csv(path)
        raw_tables[name] = df
        ingestion_metadata[name] = {
            "source_type": "csv_file",
            "source_path": str(path),
            "row_count": len(df),
            "col_count": len(df.columns),
            "columns": list(df.columns)
        }
        logger.info("Ingested CSV file '%s': %d rows, %d columns", name, len(df), len(df.columns))

    # Ingest JSON Metric Definitions if available
    json_path = DATA_DIR / "client_metric_definitions.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            ingestion_metadata["client_metric_definitions"] = json.load(f)

    # Ingest Model Brief if available
    brief_path = DATA_DIR / "class7_model_brief.json"
    if brief_path.exists():
        with open(brief_path, "r", encoding="utf-8") as f:
            ingestion_metadata["model_brief"] = json.load(f)

    logger.info("Multi-modal ingestion completed successfully. Total datasets: %d", len(raw_tables))
    return raw_tables, ingestion_metadata
