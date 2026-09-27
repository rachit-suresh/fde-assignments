# FlashEats: Executive Investigation & AI Investment Recommendation

**Topic:** Operational Claim Evaluation: *"Traffic is the problem"* | Telemetry Root-Cause Analysis  
**Role:** Forward Deployed Engineer (FDE)  
**Date:** September 27, 2026  
**Audience:** FlashEats Executive Leadership & Board of Directors  
**Decision:** **HALT AI DELAY-PREDICTOR INVESTMENT**

---

## Executive Presentation Brief (Portrait Mode — 8.5in × 11in)

The brief has been compiled into **[FINAL_FDE_SYNTHESIS_SLIDE.pdf](file:///c:/Users/admin/OneDrive/Desktop/CODE/fde/class_5/flasheats-classroom-pack/FINAL_FDE_SYNTHESIS_SLIDE.pdf)** (strictly 1-page executive portrait layout with embedded high-resolution charts).

### Core Metrics Summary

| Operational Metric | Target / SLA Standard | Actual Observed Performance | Variance / Deficit |
|---|:---:|:---:|:---:|
| **On-Time Delivery Rate** | 90.0% | **43.4%** (665 / 1,532 orders) | **-46.6% SLA Breach** |
| **Late Delivery Rate** | $\le$ 10.0% | **56.6%** (867 / 1,532 orders) | +46.6% Failure Rate |
| **Median Delay (Late Subset)** | 0.0 min | **+7.9 minutes** (Mean: +13.6 min) | Tail reaches +50.3 min |
| **Order Cancellations** | 0.0% | **4.25%** (68 orders dropped) | Total Demand Destruction |

---

## Slide Content in Simplified Technical English

### 1. Problem Sizing (Census Data)
* **Population:** 1,532 completed deliveries (3 duplicate order records removed; 37 missing drop-off timestamps recovered from driver telemetry).
* **SLA Performance:** FlashEats delivers only 43.4% of orders on time, failing the 90.0% contractual standard.
* **Delay Magnitude:** Median late order arrives 7.9 minutes after promised ETA. The slowest 5% of orders arrive over 30 minutes late.
* **Cancellations:** 68 orders (4.25%) were cancelled before fulfillment due to excessive wait times.

### 2. Data Governance & Source Quality
* **Database (`orders` in SQLite):** Reliable for order placement and initial ETA. Contained 3 duplicate rows and 37 missing delivery timestamps.
* **Driver Telemetry (`driver_events.json`):** Primary ground truth for physical delivery completion and courier assignment.
* **Dispatch API:** 100% retrieved (1,600 records across 32 pages). Captured driver reassignment churn and dynamic ETA changes.
* **Restaurant Status (`restaurant_status.csv`):** Untrusted. Covers only 31.2% of orders (500 / 1,600). Manual tablet clicks by staff are delayed and inaccurate.

### 3. Claim Evaluation: *"Traffic is the Problem"*
* **Claim is Refuted by Data:**
  * 50.1% of orders fail under **low traffic** conditions.
  * 53.6% of orders fail in **clear weather**.
  * Low and medium traffic represent 63.4% of all deliveries.
* **Distance is Not Significant:** Deliveries under 5 km fail at 55.6% (Chi-square test p-value = 0.419). Traffic increases delay severity by ~3 minutes, but is not the root cause.

### 4. Timeline Decomposition: Where Time is Lost
* **Pre-Pickup Phase (`created_at` to `pickup_at`):**
  * Absorbs **+14.2 minutes (77.4%)** of total excess delivery delay.
* **In-Transit Phase (`pickup_at` to `actual_delivery_at`):**
  * Expands by only **+4.1 minutes (22.6%)** of total excess delay.
* **Customer Support Confirmation:** 49.3% of tickets cite kitchen delays and unassigned couriers; 18.4% cite changing ETAs.

### 5. The Critical Telemetry Blindspot
```
  [ Order Placed ] ──► [ Driver Assigned ] ──► [ ? DRIVER ARRIVAL & COOKING ? ] ──► [ Picked Up ] ──► [ Delivered ]
                                                       ▲
                                            CRITICAL BLINDSPOT
                                     (77.4% of delay occurs here)
```
* **Missing Arrival Timestamp:** Telemetry has zero records of when drivers arrive at restaurants.
* **Coarse GPS Telemetry:** GPS pings occur every 13.4 minutes on average. This interval is wider than the typical 5–10 minute restaurant wait.
* **Attribution Gap:** We cannot determine if food is waiting for drivers, or if drivers are waiting for food.

### 6. Recommendations & AI Investment Decision
* **Action 1 (P0):** Add geofenced driver arrival tracking (100m radius around restaurant) to measure courier arrival automatically.
* **Action 2 (P0):** Add a +12 minute buffer to pre-pickup ETA formulas to stop ETA slipping and restore customer trust.
* **Action 3 (P1):** Connect restaurant Point-of-Sale (POS) systems to capture kitchen cooking start and food ready events.
* **Decision on AI Delay Predictor:** **DO NOT BUILD THE AI MODEL TODAY.**
  * *Reason:* Without driver arrival data, any machine learning model will confuse kitchen delays with courier delays. This will generate incorrect delay predictions and assign unfair penalties to couriers and merchants.
  * *Next Review:* Re-evaluate machine learning after collecting 60 days of geofenced arrival telemetry.
