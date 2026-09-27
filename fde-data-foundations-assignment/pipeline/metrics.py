"""
KPI Business Metrics & Diagnostic Analytics Module (Class 7 & Class 8)
Computes the 5 core business metrics linked to the project KPI (Reduce Late Delivery Rate),
constructs executive scorecards, and performs causal / diagnostic analysis.
"""
import logging
from typing import Dict, Any, Tuple
import pandas as pd
from pipeline.config import SEVERE_LATE_THRESHOLD_MIN

logger = logging.getLogger("FlashEatsPipeline.Metrics")

def calculate_kpi_metrics(
    full_workflow_mart: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Computes 5 business metrics meeting the assignment requirement:
    - At least one outcome metric
    - At least one customer interaction metric
    - At least one operational intervention metric
    
    Returns:
        metrics_scorecard_df: Formatted scorecard DataFrame for reporting.
        analytics_diagnostics: Deep-dive diagnostics including restaurant concentration
                               and intervention breakdowns.
    """
    logger.info("Computing 5 business metrics linked to Project KPI: REDUCE LATE RATE...")
    total_orders = len(full_workflow_mart)
    valid_delivered = full_workflow_mart[full_workflow_mart["delivered_flag"] == 1].copy()
    intervened_delivered = valid_delivered[valid_delivered["intervention_count"] > 0].copy()

    # Metric 1: Severe Late Delivery Rate (>10 min delay) [OUTCOME]
    severe_late_cnt = (valid_delivered["delay_min"] > SEVERE_LATE_THRESHOLD_MIN).sum()
    severe_late_rate = severe_late_cnt / len(valid_delivered)

    # Metric 2: Customer Anxiety Velocity [INTERACTION]
    total_eta_views = full_workflow_mart["eta_views"].sum()
    anxiety_velocity = total_eta_views / total_orders

    # Metric 3: Operational Intervention Coverage Rate [INTERVENTION]
    total_intervened = (full_workflow_mart["intervention_count"] > 0).sum()
    intervention_coverage = total_intervened / total_orders

    # Metric 4: Customer Support Escalation Rate [INTERACTION]
    total_support_escalations = (full_workflow_mart["support_opened"] == 1).sum()
    support_escalation_rate = total_support_escalations / total_orders

    # Metric 5: Intervention Rescue Success Rate [INTERVENTION]
    rescued_cnt = (intervened_delivered["late_flag"] == 0).sum()
    rescue_success_rate = rescued_cnt / len(intervened_delivered) if len(intervened_delivered) > 0 else 0.0

    scorecard_data = [
        {
            "Metric Name": "Severe Late Delivery Rate (>10m)",
            "Category": "Outcome",
            "Observed Value": f"{severe_late_rate:.2%}",
            "Numerator / Denominator": f"{severe_late_cnt} / {len(valid_delivered)} delivered orders",
            "Formula": "Count(delay_min > 10m) / Count(delivered_orders)",
            "Grain": "Order level",
            "Strategic Intent": "Primary outcome: Target high-churn delivery failures destroying customer retention"
        },
        {
            "Metric Name": "Customer Anxiety Velocity",
            "Category": "Interaction",
            "Observed Value": f"{anxiety_velocity:.2f} views / order",
            "Numerator / Denominator": f"{total_eta_views} ETA views / {total_orders} placed orders",
            "Formula": "Sum(ETA_VIEWED actions) / Count(placed_orders)",
            "Grain": "Order level",
            "Strategic Intent": "Leading indicator: Early-warning proxy for perceived customer friction"
        },
        {
            "Metric Name": "Intervention Coverage Rate",
            "Category": "Intervention",
            "Observed Value": f"{intervention_coverage:.2%}",
            "Numerator / Denominator": f"{total_intervened} / {total_orders} placed orders",
            "Formula": "Count(orders with intervention > 0) / Count(placed_orders)",
            "Grain": "Order level",
            "Strategic Intent": "Operational lever: Measure dispatch reach across active delivery workflows"
        },
        {
            "Metric Name": "Support Escalation Rate",
            "Category": "Interaction",
            "Observed Value": f"{support_escalation_rate:.2%}",
            "Numerator / Denominator": f"{total_support_escalations} / {total_orders} placed orders",
            "Formula": "Count(support_opened == 1) / Count(placed_orders)",
            "Grain": "Order level",
            "Strategic Intent": "Cost & friction proxy: Quantifies unmanaged delays turning into support overhead"
        },
        {
            "Metric Name": "Intervention Rescue Success Rate",
            "Category": "Intervention",
            "Observed Value": f"{rescue_success_rate:.2%}",
            "Numerator / Denominator": f"{rescued_cnt} / {len(intervened_delivered)} intervened delivered",
            "Formula": "Count(intervened & late_flag == 0) / Count(intervened delivered)",
            "Grain": "Order level",
            "Strategic Intent": "Operational efficiency: Measure proportion of intervened orders saved from SLA breach"
        }
    ]
    metrics_scorecard_df = pd.DataFrame(scorecard_data)

    # -------------------------------------------------------------------------
    # DEEP-DIVE DIAGNOSTIC ANALYTICS
    # -------------------------------------------------------------------------
    # A. Delay by Support Escalation
    delay_by_support = valid_delivered.groupby("support_opened")["delay_min"].agg(
        order_count="count",
        mean_delay="mean",
        median_delay="median",
        p75_delay=lambda s: s.quantile(0.75),
        max_delay="max"
    ).reset_index()

    # B. Intervention Efficacy & Selection Bias
    int_comp = valid_delivered.groupby("has_intervention")["late_flag"].agg(
        total_orders="count",
        late_orders="sum",
        late_rate="mean"
    ).reset_index()

    # C. Intervention Type Comparison
    type_comp = valid_delivered[valid_delivered["has_intervention"] == 1].groupby("first_intervention")["late_flag"].agg(
        total_intervened="count",
        late_count="sum",
        late_rate="mean"
    ).reset_index().sort_values("late_rate", ascending=True)

    # D. Top Late Restaurants
    rest_late = valid_delivered[valid_delivered["late_flag"] == 1].groupby("restaurant_id").agg(
        late_order_count=("order_id", "count"),
        median_delay_min=("delay_min", "median"),
        p90_delay_min=("delay_min", lambda s: s.quantile(0.90))
    ).reset_index().sort_values("late_order_count", ascending=False).head(5)

    # E. Compounding Friction Journeys (Support + Intervention + Still Late)
    friction_journeys = valid_delivered[
        (valid_delivered["support_opened"] == 1) & 
        (valid_delivered["has_intervention"] == 1) & 
        (valid_delivered["late_flag"] == 1)
    ]

    analytics_diagnostics = {
        "delay_by_support": delay_by_support.to_dict(orient="records"),
        "intervention_comparison": int_comp.to_dict(orient="records"),
        "intervention_type_comparison": type_comp.to_dict(orient="records"),
        "top_late_restaurants": rest_late.to_dict(orient="records"),
        "compounding_friction_count": len(friction_journeys)
    }

    logger.info("KPI metrics computed: Severe late rate = %s, Rescue success = %s",
                scorecard_data[0]["Observed Value"], scorecard_data[4]["Observed Value"])
    return metrics_scorecard_df, analytics_diagnostics
