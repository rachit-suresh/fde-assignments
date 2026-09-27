# FlashEats — FDE Data Foundations Final Project Submission
**Classes 4–8 | From Messy Client Data to a Dependable Business Pipeline**  
**Repository Track:** Track A — FlashEats-Style Late Delivery Optimization  
**GitHub Repository:** [fde-assignments (main)](https://github.com/rachit-suresh/fde-assignments.git)

---

## 1. Executive Summary & Problem Statement

FlashEats is experiencing high customer churn driven by unmanaged delivery delays. Operational telemetry is scattered across multiple disconnected source systems: transactional databases, customer mobile app clickstream logs, support CRM tickets, and logistics dispatch intervention events.

As the Forward Deployed Engineer (FDE), the objective was to:
1. Map and integrate fragmented multi-system data sources.
2. Establish transparent, non-silent data quality validation gates.
3. Model the business workflow into a canonical order-level mart.
4. Calculate 5 trustworthy business metrics directly tied to the primary KPI: **Reduce Late Delivery Rate**.
5. Build an automated, dependable, and repeatable pipeline that reproduces the final output from raw inputs.

---

## 2. Stakeholders & Business Decision Support

| Stakeholder Persona | Core Business Objective | Key Decision Supported by Pipeline Outputs |
|---|---|---|
| **VP of Operations & Dispatch** | Reduce SLA delivery breaches and optimize courier utilization | Determine when and how to deploy interventions (e.g. `PRIORITY_DISPATCH` vs `DRIVER_REASSIGNMENT`) proactively rather than reactively. |
| **Head of Customer Experience (CX)** | Minimize customer friction, ticket volume, and churn | Identify the threshold where customer anxiety turns into support tickets (e.g. >10 min delay; >2 ETA views). |
| **Merchant Partnerships Director** | Maintain kitchen turnaround SLAs | Identify merchant bottlenecks (e.g. Top 5 delay restaurants) for kitchen process interventions. |
| **Core Engineering & Data Platform** | Ensure data dependability and system visibility | Transition from ad-hoc analysis to a dependable, tested, automated pipeline with audit logging and anomaly reporting. |

---

## 3. Source Systems Map & Ownership Matrix

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        FLASHEATS SOURCE SYSTEMS                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│     ORDERS_DB     │     │   APP TELEMETRY   │     │  SUPPORT & DISPATCH│
│ SQLite Relational │     │  CSV Clickstream  │     │ CSV Event Streams │
│ Core Platform Eng │     │ Mobile Client Eng │     │ CX & Logistics Ops│
└───────────────────┘     └───────────────────┘     └───────────────────┘
```

| Source System | Ingestion Mode | Owning Team | Declared Grain | Business Scope & Key Attributes |
|---|---|---|---|---|
| **`orders_db.orders`** | SQLite Table | Core Platform Engineering | 1 row = 1 order placement | Order timestamps (`created_at`, `promised_eta`, `pickup_at`, `actual_delivery_at`), courier and restaurant IDs. |
| **`orders_db.customers`**| SQLite Table | User Account Services | 1 row = 1 customer profile | Registration date, customer tier, contact info. |
| **`orders_db.restaurants`**| SQLite Table | Merchant Operations | 1 row = 1 restaurant partner | Merchant cuisine, address, prep capacity baseline. |
| **`orders_db.drivers`** | SQLite Table | Courier Logistics | 1 row = 1 driver | Vehicle type, driver rating, active shift status. |
| **`customer_app_actions`**| CSV Telemetry | Mobile / Frontend Team | 1 row = 1 app interaction | Customer actions: `ETA_VIEWED`, `SUPPORT_OPENED`, `CANCEL_ATTEMPTED`. |
| **`support_tickets`** | CSV Event Log | Customer Experience (CX) | 1 row = 1 support ticket | Complaint category, customer message, timestamp. |
| **`order_interventions`**| CSV Event Log | Dispatch Automation / Ops | 1 row = 1 operational action | Intervention type (`DRIVER_REASSIGNMENT`, `PRIORITY_DISPATCH`), initiator. |
| **`order_outcomes`** | CSV Data Mart | Analytics / Data Science | 1 row = 1 final outcome | Delivery status, `late_flag`, `delay_min`, outcome bucket. |

### Critical Telemetry Gaps
- **Missing Event: `driver_arrived_at_restaurant`**:
  FlashEats currently records order placement, courier pickup, and customer drop-off. Without a timestamp marking when the driver arrives at the restaurant, operations cannot separate **kitchen wait time** (slow restaurant) from **courier travel time** (slow courier).
- **Instrumentation Recommendation**: Instrument an automated mobile GPS geofence arrival event (`driver_geofence_arrival`) triggered when the driver enters within 50 meters of the restaurant.

---

## 4. Canonical Relational Architecture & Workflow Lineage

### Relational Entity-Event Model (Central Hub Spine)
To prevent cartesian join fan-out when joining 1:N event streams (app actions, support tickets, interventions), the model establishes **`orders` as the central hub spine**, aggregating child event tables to the order grain before joining.

```text
                        ┌────────────────────────┐
                        │       CUSTOMERS        │
                        │  PK: customer_id       │
                        └───────────┬────────────┘
                                    │ 1
                                    │
                                    │ N
                        ┌───────────▼────────────┐
                        │         ORDERS         │◄─────────────────────────┐
                        │  PK: order_id          │                          │
                        │  FK: customer_id       │                          │
                        │  FK: restaurant_id     │                          │
                        │  FK: driver_id         │                          │
                        └───────────┬────────────┘                          │
                                    │                                       │
          ┌─────────────────────────┼─────────────────────────┐             │ 1:1
          │ 1:N                     │ 1:N                     │ 1:N         │
          ▼                         ▼                         ▼             ▼
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐ ┌───────────────────┐
│ CUSTOMER_ACTIONS  │     │  SUPPORT_TICKETS  │     │   INTERVENTIONS   │ │  ORDER_OUTCOMES   │
│ PK: action_id     │     │ PK: ticket_id     │     │ PK: intervention_id│ │ PK: order_id     │
│ FK: order_id      │     │ FK: order_id      │     │ FK: order_id      │ │ FK: order_id      │
│ FK: customer_id   │     │                   │     │                   │ │                   │
└───────────────────┘     └───────────────────┘     └───────────────────┘ └───────────────────┘
```

### End-to-End KPI Lineage Architecture
```text
┌────────────────────────────────────────────────────────────────────────┐
│                      PROJECT KPI: REDUCE LATE RATE                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ drives
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                            OUTCOME METRICS                             │
│  • Severe Late Delivery Rate (>10m delay) [Current: 22.78%]            │
│  • Operational SLA Breach Rate (>0m delay) [Current: 55.03%]           │
│  • Order Cancellation Rate [Current: 4.25%]                            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ influenced by
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        WORKFLOW & DRIVER METRICS                       │
│  • Customer Anxiety Velocity (Avg 1.39 ETA views per order)            │
│  • Support Escalation Rate (18.31% of orders escalate to support)      │
│  • Merchant Kitchen Backlog & Courier Transit Variance                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ addressed through
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         OPERATIONAL LEVERS                             │
│  • Priority Dispatch (Lowest late rate: 51.16% - early courier dispatch│
│  • Driver Reassignment (Re-routes stalled deliveries: 57.82%)          │
│  • Restaurant Contact (Kitchen expedited prep: 52.78%)                 │
│  • Customer Credit (Post-facto friction appeasement: 66.67%)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ instrumented via
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES & EVENTS                        │
│  • orders_db (created_at, promised_eta, pickup_at, actual_delivery_at) │
│  • customer_app_actions (ETA_VIEWED, SUPPORT_OPENED, CANCEL_ATTEMPTED) │
│  • support_tickets (ticket_id, category, customer_message)             │
│  • order_interventions (intervention_type, initiated_by, reason)       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Data Quality Profiling & Validation Rules (Class 6)

The pipeline executes **6 business-oriented validation gates** and transparently catalogs all anomalies in `outputs/validation_report.json` instead of silently dropping data:

1. **Gate 1 — Primary Key Uniqueness:** Evaluates `orders` table. Identified 3 duplicate rows across 3 unique orders (`total_rows: 1603`, `unique_keys: 1600`). Deduplicated keeping first; logged duplicate keys to anomaly report.
2. **Gate 2 — Temporal Monotonicity:** Verifies $\text{created\_at} \le \text{pickup\_at} \le \text{actual\_delivery\_at}$. Detected 5 orders where delivery occurred before pickup (recorded as courier logging timestamp anomaly).
3. **Gate 3 — Domain Normalization:** Standardized casing across `final_status_norm` (`delivered`, `cancelled`).
4. **Gate 4 — Referential Integrity:** Verified all foreign keys across `actions`, `tickets`, `interventions`, and `outcomes` map cleanly to the clean 1,600 order spine.
5. **Gate 5 — SLA Delay Consistency:** Re-calculated physical delay $(\text{delivery\_at} - \text{promised\_eta})$ and verified 100% agreement with `delay_min` and `late_flag`.
6. **Gate 6 — Quarantine Logging:** Generates structured, machine-readable validation audit report (`outputs/validation_report.json`).

---

## 6. Executive KPI Business Metrics Scorecard

The pipeline produces the canonical evidence scorecard (`outputs/kpi_metrics_scorecard.csv`) containing 5 metrics linked to the project KPI:

| Metric Name | Category | Observed Value | Numerator / Denominator | Strategic Intent |
|---|---|:---:|---|---|
| **Severe Late Delivery Rate (>10m)** | **Outcome** | **22.78%** | 349 / 1,532 delivered orders | Primary outcome: Target high-churn delays that severely damage customer retention. |
| **Customer Anxiety Velocity** | **Interaction** | **1.39 views/order** | 2,217 ETA views / 1,600 orders | Leading indicator: Real-time proxy for customer friction before an SLA breach occurs. |
| **Intervention Coverage Rate** | **Intervention** | **26.88%** | 430 / 1,600 placed orders | Operational reach: Measures proportion of active workflows receiving dispatch attention. |
| **Support Escalation Rate** | **Interaction** | **18.31%** | 293 / 1,600 placed orders | Cost & friction proxy: Quantifies unmanaged delivery delays turning into support tickets. |
| **Intervention Rescue Success Rate** | **Intervention** | **42.93%** | 176 / 410 intervened delivered | Operational efficiency: Measures proportion of intervened orders successfully delivered on time. |

### Diagnostic Findings:
- **Delay by Support Escalation:** Orders with support contact suffer **median delay of +12.29m** (mean +12.72m) vs **-0.25m** for unescalated orders.
- **Top 5 Late Restaurants:** `R050` (22 late orders), `R004` (20), `R024` (20), `R023` (20), `R030` (20).
- **Compounding Friction Journeys:** Exactly **67 orders** experienced support escalation + operational intervention + still arrived late.
- **Unserved Frustrated Orders:** **191 late orders** had support contact but received zero operational intervention.

---

## 7. Known / Unknown / Assumptions / Limitations Matrix

| Dimension | Description & Project Context |
|---|---|
| **Known** | 1,600 orders placed; 1,532 delivered; 843 late (>0m); 349 severe late (>10m); 430 received operational interventions; 293 contacted support. |
| **Unknown** | Exact split between kitchen wait time and courier transit time (due to missing `driver_arrived_at_restaurant` telemetry). |
| **Assumption** | Deliveries exceeding promised ETA by $\le 10$ minutes represent normal urban transit variance; churn is predominantly driven by severe delays ($>10$ minutes). |
| **Limitation** | Observational historical data cannot provide counterfactual outcomes (what would have happened if an unmanaged order had received priority dispatch). |

---

## 8. Pipeline Setup, Replication & Testing Instructions

### Project Structure
```text
fde-data-foundations-assignment/
├── FDE_Assignment2.pdf                  <- Assignment brief
├── README.md                           <- This executive submission report
├── pipeline/                           <- Modular Python pipeline
│   ├── config.py                       <- Paths, SLA thresholds, schema constants
│   ├── ingest.py                       <- Multi-modal ingestion (SQL + CSV/JSON)
│   ├── validate.py                     <- 6 Data quality gates & anomaly profiling
│   ├── transform.py                    <- Canonical order hub & workflow mart builder
│   ├── metrics.py                      <- 5 Business KPI metrics calculator
│   └── run_pipeline.py                 <- CLI entry point (ingest -> validate -> transform -> metrics)
├── notebooks/
│   └── FlashEats_Final_Submission.ipynb <- Master runnable notebook with complete outputs
├── tests/
│   └── test_pipeline.py                <- Automated unit and integration test suite
└── outputs/                            <- Generated deliverables & artifacts
    ├── pipeline_execution.log          <- Execution log with timestamps
    ├── validation_report.json          <- Machine-readable validation audit report
    ├── order_workflow_mart.csv         <- Canonical single-order workflow mart (1,600 x 9)
    └── kpi_metrics_scorecard.csv       <- Executive scorecard with observed KPI metrics
```

### Quick Start Commands
Run the complete pipeline from the workspace root or assignment folder:

```bash
# 1. Execute the repeatable pipeline end-to-end
python fde-data-foundations-assignment/pipeline/run_pipeline.py

# 2. Run the automated test suite
python fde-data-foundations-assignment/tests/test_pipeline.py

# 3. Optional: Run in strict mode (fails if any validation anomalies are detected)
python fde-data-foundations-assignment/pipeline/run_pipeline.py --strict
```

---

## 9. 3–5 Minute Demo Script & FDE Judgement Call

### Talk Track: The FDE Judgement Call (Confounding by Indication)
*"Good morning leadership team. When you first inspect the raw delivery metrics, you see a counter-intuitive finding: orders with operational interventions have a **56.44% late rate**, which is virtually identical to unmanaged orders (**56.37%**).*

*A naive analyst would conclude: 'Our dispatch team is wasting time; operational interventions do not work.'*

*As an FDE, my critical judgement call was recognizing **confounding by indication (selection bias)**. Dispatchers do not intervene on random orders. They selectively intervene on deliveries that are already delayed, stalled, or off-track. Without intervention, these at-risk deliveries would not merely be 10 minutes late—they would suffer catastrophic 40+ minute delays or customer cancellation.*

*Furthermore, our canonical workflow model reveals why intervention rescue rates are only 42.9%: **interventions happen too late in the delivery cycle**. Currently, operations acts reactively after a customer files a ticket.*

*Our pipeline's recommendation is to shift intervention triggers upstream: by monitoring **Customer Anxiety Velocity** (`ETA_VIEWED` spikes) in real-time, dispatch can trigger `PRIORITY_DISPATCH` 15 minutes earlier, converting late deliveries into on-time saves before SLA breach occurs."*
