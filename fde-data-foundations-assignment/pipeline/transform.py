"""
Canonical Workflow Transformation Module (Class 7 Workflow Modeling)
Constructs the central orders hub and aggregates one-to-many event child tables
into an order-level canonical workflow mart (interaction -> intervention -> outcome).
"""
import logging
from typing import Dict, Tuple
import pandas as pd
from pipeline.config import CANONICAL_MART_COLS

logger = logging.getLogger("FlashEatsPipeline.Transform")

def build_order_workflow_mart(
    clean_tables: Dict[str, pd.DataFrame]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Transforms clean source tables into:
    1. full_workflow_mart: Enriched order table with all dimensions and event aggregates.
    2. canonical_mart: Exact 9-column target mart required by the assignment specification:
       (order_id, customer_id, support_opened, cancel_attempted, intervention_count,
        intervention_types, final_status, late_flag, delay_min).
        
    Guarantees strict single-order grain (1,600 rows) preventing cartesian fan-out.
    """
    logger.info("Transforming tables into canonical workflow model...")
    orders = clean_tables["orders"]
    actions = clean_tables["customer_app_actions"]
    tickets = clean_tables["support_tickets"]
    interventions = clean_tables["order_interventions"]
    outcomes = clean_tables["order_outcomes"]

    # 1. Aggregate Customer Actions to Order Grain (1 : N -> 1 : 1)
    actions_agg = actions.groupby("order_id").agg(
        action_count=("action_id", "count"),
        app_support_opened=("action_type", lambda s: int((s == "SUPPORT_OPENED").any())),
        cancel_attempted=("action_type", lambda s: int((s == "CANCEL_ATTEMPTED").any())),
        eta_views=("action_type", lambda s: int((s == "ETA_VIEWED").sum()))
    ).reset_index()

    # 2. Aggregate Support Tickets to Order Grain (1 : N -> 1 : 1)
    tickets_agg = tickets.groupby("order_id").agg(
        ticket_count=("ticket_id", "count"),
        has_ticket=("ticket_id", lambda s: 1)
    ).reset_index()

    # 3. Aggregate Operational Interventions to Order Grain (1 : N -> 1 : 1)
    interventions_agg = interventions.groupby("order_id").agg(
        intervention_count=("intervention_id", "count"),
        intervention_types=("intervention_type", lambda s: "; ".join(sorted(s.unique()))),
        first_intervention=("intervention_type", "first"),
        primary_initiator=("initiated_by", "first")
    ).reset_index()

    # 4. Join onto Order Spine and Outcomes (Guaranteed 1:1 Grain)
    full_workflow_mart = outcomes.merge(
        orders[["order_id", "customer_id", "restaurant_id", "driver_id", 
                "created_at", "promised_eta", "pickup_at", "actual_delivery_at"]],
        on="order_id",
        how="left"
    ).merge(
        actions_agg,
        on="order_id",
        how="left"
    ).merge(
        tickets_agg,
        on="order_id",
        how="left"
    ).merge(
        interventions_agg,
        on="order_id",
        how="left"
    )

    # 5. Handle Null Values and Format Indicators
    full_workflow_mart["action_count"] = full_workflow_mart["action_count"].fillna(0).astype(int)
    full_workflow_mart["app_support_opened"] = full_workflow_mart["app_support_opened"].fillna(0).astype(int)
    full_workflow_mart["cancel_attempted"] = full_workflow_mart["cancel_attempted"].fillna(0).astype(int)
    full_workflow_mart["eta_views"] = full_workflow_mart["eta_views"].fillna(0).astype(int)

    full_workflow_mart["ticket_count"] = full_workflow_mart["ticket_count"].fillna(0).astype(int)
    full_workflow_mart["has_ticket"] = full_workflow_mart["has_ticket"].fillna(0).astype(int)

    full_workflow_mart["intervention_count"] = full_workflow_mart["intervention_count"].fillna(0).astype(int)
    full_workflow_mart["intervention_types"] = full_workflow_mart["intervention_types"].fillna("NONE")
    full_workflow_mart["has_intervention"] = (full_workflow_mart["intervention_count"] > 0).astype(int)
    full_workflow_mart["first_intervention"] = full_workflow_mart["first_intervention"].fillna("NONE")

    # Unified support contact flag: either in-app support opened OR formal ticket opened
    full_workflow_mart["support_opened"] = (
        (full_workflow_mart["app_support_opened"] == 1) | (full_workflow_mart["has_ticket"] == 1)
    ).astype(int)
    full_workflow_mart["final_status"] = full_workflow_mart["final_status_norm"]

    # 6. Extract Canonical 9-Column Mart
    canonical_mart = full_workflow_mart[CANONICAL_MART_COLS].copy()

    logger.info("Transformation complete. Mart shape: %s, Unique orders: %d", 
                str(canonical_mart.shape), canonical_mart["order_id"].nunique())
    return full_workflow_mart, canonical_mart
