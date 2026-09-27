# Challenge 2 Investigation Methodology & Graph Navigation Report

**Project:** FlashEats Classroom Investigation — Class 5  
**Topic:** Challenge 2: Evaluating the Operational Claim — *"Traffic is the problem."*  
**Role:** Forward Deployed Engineer (FDE)  
**Date:** September 24, 2026  

---

## Executive Summary

When confronted with the operational hypothesis *"Traffic is the problem,"* we navigated a structured 6-phase analytical decision tree to evaluate whether empirical telemetry supports or refutes this claim. 

By applying disciplined FDE methodology—enforcing denominator integrity, testing for both failure probability (Risk) and magnitude (Severity), avoiding volume skew traps, and performing process mining timeline decomposition—we uncovered a critical operational truth:
1. **Traffic is not the root cause:** Even under free-flowing (`low`) traffic conditions, **50.14% of orders are late**, and in clear weather, **53.56% of orders fail**.
2. **The Pre-Pickup Blowout:** Decomposing order timelines revealed that **77.4% of the excess delay (+14.15 minutes)** occurs in the pre-pickup phase (`created_at` to `pickup_at`), while transit time on the road only expands by **+4.12 minutes (22.6%)**.
3. **Instrumentation Blindspot:** Because telemetry lacks a `driver_arrived_at_restaurant` hardware/app ping, the business cannot currently disentangle kitchen cooking delays from driver dwell time. An AI delay-prediction model must not be built until this telemetry gap is resolved.

---

## The Decision Tree Navigation & Node-by-Node Analysis

```text
  [ Anomaly: "Customers complain about late deliveries" ]
                         │
                         ▼
  [ Phase 1: Population & Target Metrics ]
         │
         ├─► [ 1.1 Denominator Selection ]
         │         │
         │         ▼
         │   { Trap Check: Only Failures? } ──YES (Selection Bias)──► [ STOP ]
         │         │
         │        NO (All Delivered Orders: N=1,532)
         │         │
         │         ▼
         └─► [ 1.2 Target Metrics: Risk (Late Rate %) & Severity (Median Delay) ]
                         │
                         ▼
  [ Phase 2: Baseline Quantification ]
         │
         ├─► [ 2.1 Global Census: 56.59% Late ]
         ├─► [ 2.2 Verified Full Population: N = 1,532 ]
         └─► [ 2.3 SLA Deficit: -46.59% vs 90% SLA Standard ]
                         │
                         ▼
  [ Phase 3: Disaggregate & Compare ]
         │
         ├─► [ 3.1 Dimension Grouping: Traffic, Weather, Distance ]
         ├─► [ 3.2 Test Risk: Chi-Square Test (Low vs Severe) ]
         ├─► [ 3.3 Test Severity: Kruskal-Wallis Test ]
         │         │
         │         ▼
         │   { Trap Check: Volume Skewed? } ──YES──► Normalize Rates
         │         │
         │         ▼
         └─► [ Inference: 50.14% Late in LOW Traffic! Traffic is an amplifier, not root cause ]
                         │
                         ▼
  [ Phase 4: Process Mining Timeline ]
         │
         ├─► [ 4.1 Decompose Phases: Prep vs Transit ]
         ├─► [ 4.2 Quantify Delay Absorption: 77.4% excess delay (+14.15m) in Pre-Pickup ]
         │         │
         │         ▼
         │   { Trap Check: Telemetry Exists for Prep Breakdown? }
         │         │
         │        NO (Critical Blindspot: No driver arrival ping)
         │         │
         │         ▼
         └─► [ STOP: Flag Telemetry Blindspot & Route to Phase 6 ]
                         │
                         ▼
  [ Phase 5: Isolate Causation ]
         │
         ├─► [ 5.1 Confounder Analysis: Restaurant volume, dispatch lag, driver dwell ]
         └─► [ 5.2 Association vs Causation Separation: Refute "Traffic is the problem" ]
                         │
                         ▼
  [ Phase 6: Action & Recommendations ]
         │
         ├─► [ Action 1: Deploy Geofenced Telemetry (driver_arrived_at_restaurant) ]
         ├─► [ Action 2: Recalibrate Baseline ETA Buffer (+10-15 min Pre-Pickup) ]
         └─► [ Action 3: Halt AI Delay Predictor Development until telemetry gap is closed ]
```

---

### Phase 1: Define the Population & Target Metrics

#### Node 1.1: Exact Denominator Selection
* **Decision Taken:** Defined the population strictly as all valid, deduplicated orders where `final_status == 'delivered'` (N = 1,532).
* **Why This Decision Was Made:**
  * Raw database deduplication: Identified and eliminated 3 duplicate order records (`O00120`, `O00723`, `O01302`), preventing double-counting.
  * Telemetry reconciliation: Recovered 37 delivered orders missing `actual_delivery_at` in the SQLite DB by mapping `delivered` timestamps from `driver_events.json`. Naive `dropna()` would have deleted 37 valid deliveries and distorted the denominator.
  * Cancelled orders: Excluded 68 cancelled orders (4.25% dropout rate) from the physical delivery delay calculation because delivery was never attempted/completed.
* **Trap Check (Selection Bias):**
  * *Question:* Are we only analyzing failures (late orders)?
  * *Navigation:* **NO**. If we restricted the dataset to late orders, we would introduce severe conditioning on the outcome variable (Berkson's bias / survivorship bias). We retained all 1,532 delivered orders (665 on-time, 867 late) to observe the true base rate across all operating conditions.

#### Node 1.2: Target Metric Formulation
* **Decision Taken:** Formulated three complementary metrics rather than relying on a single average:
  1. **Risk Metric (Probability of Failure):**
     `Late Rate (%) = (Late Delivered Orders / Total Delivered Orders) * 100` (where delay_min > 0)
  2. **Severity Metric (Delay Magnitude):**
     * Overall median delay across all 1,532 orders.
     * Median delay among the failure subset (delay_min > 0) to measure tail severity without mean distortion from extreme outliers.
  3. **Cost / SLA Metric:**
     * Measured distance from the contractual 90% on-time delivery commitment.

---

### Phase 2: Establish the Baseline ("How Bad Is It?")

#### Node 2.1 & 2.2: Global Population Baseline
* **Calculations & Evidence:**
  * Total Valid Delivered Orders (Full Population): N = 1,532
  * Total Late Deliveries: 867
  * **Global Late Delivery Rate:** **56.59%**
  * Overall Median Delay: +1.43 minutes
  * Median Delay (Late Orders Only): +7.94 minutes (Mean: +13.56 minutes, Max: +50.27 minutes)
* **Node 2.3: Comparison Against Business SLAs:**
  * Contractual Standard: 90.0% On-Time Rate (<= 10.0% late).
  * Observed On-Time Performance: **43.41%**.
  * **Inference:** FlashEats suffers a catastrophic **-46.59% SLA breach**. Because we hold the entire company operational record for this period, this 56.59% failure rate is an exact population truth, confirming a structural breakdown across the network.

---

### Phase 3: Disaggregate & Compare ("Where Is It Happening?")

Operations asserted: *"Traffic is the problem."* To evaluate this claim, we disaggregated the global population across four operational dimensions: **Traffic Condition**, **Weather Condition**, **Delivery Distance**, and **Restaurant Tablet Mode**.

#### Multi-Dimensional Summary Matrix

| Operational Dimension | Bucket / Stratum | Volume ($N$) | Vol % | Late Count | Late Rate (%) | Median Delay (All) | Median Delay (Late) | Risk Significance ($\chi^2$) | Severity Significance ($H$) |
|---|---|---|---|---|---|---|---|---|---|
| **Traffic Condition** | `low` | 369 | 24.1% | 185 | **50.14%** | +0.06 min | +6.93 min | Chi2 = 32.53 | H = 8.36 |
| | `medium` | 602 | 39.3% | 312 | **51.83%** | +0.45 min | +7.65 min | p = 5.64e-07 | p = 0.039 |
| | `high` | 433 | 28.3% | 286 | **66.05%** | +3.68 min | +8.36 min | *(Statistically Sig.)* | *(Statistically Sig.)* |
| | `severe` | 128 | 8.4% | 84 | **65.63%** | +4.27 min | +9.94 min | | |
| **Weather Condition** | `clear` | 1,221 | 79.7% | 654 | **53.56%** | +0.80 min | +7.36 min | Chi2 = 23.51 | H = 10.90 |
| | `rain` | 239 | 15.6% | 160 | **66.95%** | +4.15 min | +9.88 min | p = 7.97e-06 | p = 0.004 |
| | `heavy_rain` | 72 | 4.7% | 53 | **73.61%** | +6.63 min | +9.43 min | *(Statistically Sig.)* | *(Statistically Sig.)* |
| **Distance Band** | `< 5 km` | 72 | 4.7% | 40 | **55.56%** | +0.60 min | +6.30 min | Chi2 = 2.83 | H = 1.87 |
| | `5 – 10 km` | 228 | 14.9% | 128 | **56.14%** | +1.04 min | +7.58 min | p = 0.419 | p = 0.600 |
| | `10 – 15 km` | 304 | 19.8% | 160 | **52.63%** | +0.64 min | +8.39 min | *(Not Significant)* | *(Not Significant)* |
| | `> 15 km` | 928 | 60.6% | 539 | **58.08%** | +1.68 min | +7.94 min | | |
| **Vehicle Type** | `bike` | 872 | 56.9% | 496 | **56.88%** | +1.40 min | +7.44 min | Chi2 = 1.29 | H = 8.81 |
| | `ebike` | 167 | 10.9% | 100 | **59.88%** | +1.96 min | +6.26 min | p = 0.524 | p = 0.012 |
| | `scooter` | 493 | 32.2% | 271 | **54.97%** | +1.19 min | +9.50 min | *(Not Significant)* | *(Statistically Sig.)* |

#### Trap Check: Volume Skew & Base Rate Neglect
* *The Trap:* A naive observer counting raw failures would observe 497 late orders in low/medium traffic and only 84 in severe traffic, falsely concluding that low/medium traffic is "where all the problems are," or attributing delays to weather because 654 late orders occurred in clear conditions.
* *The Navigation:* We **normalized by calculating the failure rate (% Late)** per stratum.
* *The Critical Inferences:*
  1. **The 50.14% Low-Traffic Anomaly:** In completely clear, low-traffic conditions, the late rate is still **50.14%**. If traffic congestion were the causal driver of delay, low traffic would yield an on-time rate near 90–95%. A coin-flip failure rate on empty roads completely invalidates Operations' premise that traffic is the primary culprit.
  2. **The Distance Invariance:** Distance has zero statistically significant relationship with failure risk (p = 0.419) or failure severity (p = 0.600). Short trips under 5 km fail at 55.56%, identical to trips over 15 km (58.08%).
  3. **The Vehicle Type Invariance:** Vehicle selection (`bike`, `ebike`, `scooter`) does **not** change failure probability (Chi2 = 1.29, p = 0.524). Bicycles, e-bikes, and scooters all average virtually the same transit duration (~45.8 minutes) and all experience ~55–60% late rates. Scooters exhibit slightly higher tail severity (median late delay of 9.50 min vs 7.44 min on bikes, H = 8.81, p = 0.012), likely reflecting parking/traffic constraints in motorized delivery corridors.

---

### Phase 4: Decompose the Timeline (Process Mining)

#### Node 4.1: Operational Stage Breakdown
To discover where the delivery time was actually being consumed, we decomposed the total delivery lifecycle into two mutually exclusive, sequentially exhaustive intervals:

`Total Order Duration = (pickup_at - created_at) [Phase A: Prep & Dispatch] + (actual_delivery_at - pickup_at) [Phase B: Delivery Transit]`

```
Order Created              Driver Pickup                   Customer Delivery
      |                          |                                 |
      +--------------------------+---------------------------------+
          Phase A: Prep & Dispatch      Phase B: Delivery Transit
          (Kitchen cooking, driver       (Driver travel from restaurant
           dispatch & waiting)            to customer address)
```

#### Node 4.2: Quantitative Delay Absorption
Comparing on-time deliveries against late deliveries revealed the true operational bottleneck:

| Lifecycle Stage | On-Time Deliveries ($N=665$) | Late Deliveries ($N=867$) | Delta ($\Delta$) | Share of Delay Absorption |
|---|---|---|---|---|
| **Phase A: Prep & Dispatch** | **19.53 min** (median: 19.77) | **33.68 min** (median: 31.85) | **+14.15 min** | **77.4%** |
| **Phase B: Delivery Transit** | **43.45 min** (median: 45.46) | **47.57 min** (median: 48.96) | **+4.12 min** | **22.6%** |
| **Total Duration** | 62.98 min | 81.25 min | +18.27 min | 100.0% |

#### Trap Check: Telemetry Granularity & The Instrumentation Blindspot
* *The Question:* Can we decompose Phase A to determine whether the 14.15-minute expansion is caused by kitchen prep delay, dispatch assignment lag, or driver waiting at the restaurant?
* *The Investigation:*
  * We audited `driver_events.json`. Each driver record contains four event types: `assigned`, `gps_ping`, `picked_up`, and `delivered`.
  * **Critical Gap Found:** There is **NO `driver_arrived_at_restaurant` timestamp** in the telemetry.
  * Furthermore, `restaurants.csv` and `restaurant_status.csv` do not provide digital Kitchen Display System (KDS) prep completion logs (only manual, unreliable batch updates for a fraction of orders).
* *The Navigation:*
  * **STOP**. Per the decision tree: *Do I have the telemetry timestamps to actually measure this phase? NO $\rightarrow$ STOP. You have an Instrumentation Blindspot. Proceed to Phase 6.*
  * We explicitly refused to fabricate or guess kitchen prep vs. driver dwell time, recognizing this as an uninstrumented operational blindspot.

---

### Phase 5: Isolate Causation (The "Why?" Phase)

#### Node 5.1: Confounder Analysis (Traffic $\times$ Weather)
* Cross-tabulating traffic against weather demonstrated that severe traffic occurs predominantly during clear and medium conditions simply due to urban density, not merely rain:
  * High Traffic: 338 clear, 20 heavy rain, 75 rain.
  * Severe Traffic: 100 clear, 4 heavy rain, 24 rain.
* While bad weather increases the probability of high traffic, it does not explain why clear-weather, low-traffic deliveries fail over 50% of the time.

#### Node 5.2: Separation of Association from Causation
* **What is Associated:** Traffic congestion has a statistically significant correlation with higher delay severity. Severe traffic increases median delay among late orders from 6.93 min to 9.94 min ($\Delta = +3.01$ min).
* **What is NOT Causal:** Road traffic does not cause the system's baseline failure. A factor that explains only +4.12 minutes of extra transit time cannot be held responsible for an 18.27-minute total delivery blowout when +14.15 minutes occurred before the driver even touched the package.

---

### Phase 6: Instrumentation & Action (The "What Do We Do?" Phase)

Navigating to the final node of the decision tree dictates our forward deployed engineering action plan:

```
                  ┌────────────────────────────────────────────────────────┐
                  │ ROOT CAUSE HIDDEN BY TELEMETRY INSTRUMENTATION GAP?    │
                  └──────────────────────────┬─────────────────────────────┘
                                             │
                                      YES ───┴───► STOP ML INVESTMENT
                                                   1. Instrument Geofence
                                                   2. Recalibrate Base ETA
                                                   3. Audit Kitchen Hand-offs
```

#### 1. Reject Premature Machine Learning Investment
* Operations requested: *"Figure out what is happening before we invest in an AI delay-prediction system."*
* **Our FDE Verdict:** **DO NOT BUILD THE AI MODEL.**
* **Why:** Any supervised ML model trained on the current feature set (`traffic_bucket`, `weather_bucket`, `distance_km_estimate`) will suffer from omitted variable bias. The model would attempt to predict transit time variations while remaining completely blind to the pre-pickup bottleneck where 77.4% of the delay originates. Training an AI model on blind telemetry would simply automate and perpetuate inaccurate customer ETAs.

#### 2. Mandatory Instrumentation Fix
* **Implement Geofenced Telemetry:** Update the mobile driver application to emit an automated `driver_arrived_at_restaurant` event when a driver enters a 50-meter GPS radius around the restaurant.
* **Impact:** This splits Phase A into two measurable sub-phases:
  1. *Driver Travel to Restaurant* (`driver_arrived_at_restaurant` $-$ `assigned`)
  2. *Driver Restaurant Dwell Time* (`picked_up` $-$ `driver_arrived_at_restaurant`)
  If dwell time is high, the kitchen is behind schedule; if travel time is high, the dispatch engine is batching drivers inefficiently.

#### 3. Recalibrate Baseline Static ETAs
* The current promised ETA window averages ~70 minutes regardless of whether prep time takes 19 minutes or 34 minutes.
* FlashEats must introduce dynamic prep buffers tied to restaurant-specific historical prep profiles rather than assuming static instant hand-offs.

---

## Conclusion & Decision Tree Traceability Matrix

| Node | Question / Check | Decision Taken | Empirical Justification | Operational Conclusion |
|---|---|---|---|---|
| **1.1** | Denominator definition | N = 1,532 valid delivered orders | Restored grain, recovered 37 missing timestamps | Avoided selection bias and unfulfilled order distortion |
| **1.2** | Target metrics | Risk (% Late) & Severity (Median Delay) | Bounded distribution, highly skewed tail | Captures both failure frequency and operational depth |
| **2.1** | Baseline magnitude | Global 56.59% Late Rate | Exact company population census | Massive systemic SLA breach (-46.59%) |
| **3.1** | Disaggregate claim | Stratified across Traffic, Weather, Distance | Normalization per bucket | Disproved claim: 50.14% fail in Low Traffic |
| **4.1** | Timeline decomposition | Split into Prep/Dispatch vs. Transit | Process mining on timestamps | **Smoking Gun:** 77.4% of delay is pre-pickup (+14.15 min) |
| **4.2** | Sub-phase telemetry | Audit driver & restaurant events | Missing driver_arrived_at_restaurant | **STOP:** Flagged Instrumentation Blindspot |
| **5.2** | Causal attribution | Contrast transit delta vs. prep delta | +4.12 min transit vs. +14.15 min prep | Traffic is an amplifier, not the root cause |
| **6.0** | Strategic recommendation | Halt ML model; instrument geofence | Upstream data opacity | Fix data collection before building AI |
