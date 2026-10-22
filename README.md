# FreshPrice AI — Markdown Before Waste: Near-Expiry Pricing

**NEXAI 2026 Hackathon — Problem Statement 4.1 (Track 4: Grocery Retail)**  
**Repository**: [https://github.com/thilagars4767-ux/freshprice-ai](https://github.com/thilagars4767-ux/freshprice-ai)  
**Location**: `C:\freshprice`  
**Runtime**: Python 3.12+ (Windows / macOS / Linux)  
**Test Suite**: 117 tests across 7 test suites (100% passing)  

FreshPrice AI is an end-to-end, reproducible grocery retail simulation and decision-support system designed to tackle structural perishable food waste. It models 20 perishable grocery products across 4 core departments (Dairy, Bakery, Fruits, Vegetables) in a realistic single-store operational environment, comparing standard Fixed-Price retail baselines against Near-Expiry Markdown Policies, Category-Specific Clearance Optimizers, and Demand-Aware Algorithmic Pricing.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Hackathon Problem Statement (PS 4.1)](#2-hackathon-problem-statement-ps-41)
3. [Key Features](#3-key-features)
4. [Architecture & File Structure](#4-architecture--file-structure)
5. [Setup Instructions](#5-setup-instructions)
6. [Dependencies](#6-dependencies)
7. [How to Launch the Dashboard](#7-how-to-launch-the-dashboard)
8. [How to Run Tests](#8-how-to-run-tests)
9. [Product Catalog & Synthetic Data](#9-product-catalog--synthetic-data)
10. [Data Schemas & Column Descriptions](#10-data-schemas--column-descriptions)
11. [Inventory Batch Assumptions](#11-inventory-batch-assumptions)
12. [Shelf-Life Assumptions](#12-shelf-life-assumptions)
13. [Replenishment Rules](#13-replenishment-rules)
14. [First-Expiry-First-Out (FEFO) Depletion Behavior](#14-first-expiry-first-out-fefo-depletion-behavior)
15. [The 4-Step Simulation Pipeline (Stock → Demand → Pricing → Evaluation)](#15-the-4-step-simulation-pipeline-stock--demand--pricing--evaluation)
16. [Demand Equation, Sensitivity Multiplier & Modeling Precision](#16-demand-equation-sensitivity-multiplier--modeling-precision)
17. [Random Seed & Reproducibility](#17-random-seed--reproducibility)
18. [Policy A: Fixed-Price Baseline](#18-policy-a-fixed-price-baseline)
19. [Policy B: Markdown Policies (Graduated Rule & Demand-Aware)](#19-policy-b-markdown-policies-graduated-rule--demand-aware)
20. [Category-Specific Markdown Optimizer](#20-category-specific-markdown-optimizer)
21. [Shopper Discount-Response Sensitivity Analysis](#21-shopper-discount-response-sensitivity-analysis)
22. [Shopper-Facing Portal: "Today's Fresh Deals"](#22-shopper-facing-portal-todays-fresh-deals)
23. [Minimum Gross Margin Floor Calculation](#23-minimum-gross-margin-floor-calculation)
24. [Revenue & Accounting Formulas (GAAP Compliant)](#24-revenue--accounting-formulas-gaap-compliant)
25. [Waste Cost Treatment: GAAP vs. Net Contribution](#25-waste-cost-treatment-gaap-vs-net-contribution)
26. [Fair-Comparison Methodology](#26-fair-comparison-methodology)
27. [Historical Price Analysis (365 Days)](#27-historical-price-analysis-365-days)
28. [Known Limitations](#28-known-limitations)
29. [Example Experiment Workflow](#29-example-experiment-workflow)

---

## 1. Project Overview

Perishable grocery retail operates under tight operating margins (15%–35%) and severe spoilage risk. High-velocity perishable categories—fresh dairy, sliced bread, artisanal buns, berries, and leafy greens—spoil within 2 to 8 days of store arrival. Under conventional fixed-price retail operations, products sit on shelves at full sticker price until expiration. Customers naturally select newer packages, leaving older batches to expire unsold. This creates deadweight economic loss and environmental food waste.

**FreshPrice AI** solves this operational challenge through:
1. **Perishable Store Simulator (`src/store_simulator.py`)**: A discrete-event inventory simulator tracking batch-level First-Expiry-First-Out (FEFO) arrivals, daily demand stochasticity, customer price elasticity, and morning expiry purges.
2. **Clearance Pricing Engine (`src/pricing_engine.py` & `src/discount_optimizer.py`)**: Rule-based graduated markdowns and econometric demand-aware optimization ensuring selling prices never breach wholesale cost or retailer margin floors ($P \ge C / (1 - m)$).
3. **Category-Specific Markdown Optimizer (`src/category_optimizer.py`)**: Multi-seed algorithmic evaluator testing departmental clearance schedules to maximize Net Contribution after Waste Cost.
4. **Interactive Streamlit Dashboard (`src/dashboard.py`)**: A professional, Zomato-inspired red-and-white executive UI delivering side-by-side policy comparisons, executive KPI cards, batch lifecycle audits, SKU clearance recommendations, 365-day price history graphs, and a Shopper-Facing "Today's Fresh Deals" storefront portal.

---

## 2. Hackathon Problem Statement (PS 4.1)

- **Hackathon**: NEXAI 2026
- **Track**: Track 4 — Grocery Retail
- **Problem Statement**: PS 4.1 — Near-Expiry Pricing / Markdown Before Waste
- **Target Deliverable**: A working MVP demonstrating that dynamic, near-expiry clearance pricing significantly curtails physical grocery waste while preserving gross margin and profitability.

---

## 3. Key Features

- **20 Perishable SKUs Across 4 Categories**: 5 Dairy, 5 Bakery, 5 Fruits, 5 Vegetables with realistic Indian grocery retail price points denominated in **INR (₹)**.
- **Compact Executive KPI Row**: Real-time display of Waste Reduction %, Revenue Change (INR), Net Contribution Gain (INR), and Gross Margin Change in percentage points (`pp`).
- **Category-Specific Markdown Optimizer**: Multi-seed optimization evaluating tailored clearance schedules for Dairy, Bakery, Fruits, and Vegetables.
- **Shopper Discount-Response Sensitivity Control**: Adjustable multiplier ($\gamma \in [0.25, 1.25]$) evaluating model robustness under dampened demand elasticity.
- **Shopper-Facing Fresh Deals Portal**: Real-time customer storefront view showcasing active clearance bargains with verified in-stock availability and zero expired items.
- **Strict Shelf-Life-Aware Guardrails**: Short-lived products (e.g., 3-day milk, pav, palak) do not trigger premature 2-day markdowns on day 1.
- **Fair-Comparison Experimental Framework**: Both policies run on identical initial inventory, identical scheduled replenishment batches, and identical pre-generated baseline customer demand draws.
- **Full GAAP Reconciliation**: Enforces physical inventory conservation ($\text{Received} = \text{Sold} + \text{Wasted} + \text{Ending}$) and transparently reports GAAP Gross Profit alongside Operational Net Contribution after Waste Cost.
- **Light Red-and-White UI**: Crisp, high-contrast Zomato red (`#E23744`), pure white (`#FFFFFF`), light gray (`#F8F8F8`), and charcoal (`#222222`) design with zero raw HTML styling bugs.

---

## 4. Architecture & File Structure

```text
C:\freshprice\
├── data/                                   # Synthetic benchmark datasets & simulation exports
│   ├── products.csv                        # 20 SKU master catalog definitions
│   ├── historical_product_demand.csv       # 365-day historical demand dataset (7,300 rows)
│   ├── product_price_history.csv           # 365-day price changes & rationale (7,300 rows)
│   ├── inventory_batch_history.csv         # Batch arrival, expiry & FEFO tracking (3,953 batches)
│   ├── daily_store_history.csv             # 365-day reconciled store financial ledger
│   ├── mvp_products.csv                    # 20-product simulation catalog export
│   ├── daily_simulation_history.csv        # 30-day product operational log (1,200 rows)
│   ├── policy_comparison_summary.csv       # 14-metric GAAP policy comparison table
│   ├── markdown_events_history.csv         # Audit log of dynamic price adjustments
│   └── product_markdown_recommendations.csv# 14-column SKU clearance optimization table
├── src/                                    # Core application modules
│   ├── __init__.py
│   ├── store_simulator.py                  # 30-day discrete-event store simulator
│   ├── dashboard.py                        # Streamlit web UI & Shopper Deals storefront
│   ├── category_optimizer.py               # Multi-seed category-specific clearance optimizer
│   ├── demand_estimator.py                 # OLS regression baseline demand & elasticity
│   ├── discount_optimizer.py               # Discrete candidate markdown optimization
│   ├── demand_history.py                   # 365-day synthetic grocery dataset generator
│   ├── pricing_engine.py                   # Financial identities & pricing constraints
│   ├── performance_analysis.py             # Sensitivity analysis & category aggregations
│   └── data_generator.py                   # Catalog initialization & schema helpers
├── tests/                                  # Automated test suite (112 tests)
│   ├── __init__.py
│   ├── test_category_optimizer.py          # 4 tests: Multi-category optimization & reporting
│   ├── test_store_simulator.py             # 26 tests: Conservation, FEFO, sensitivity multiplier
│   ├── test_dashboard.py                   # 27 tests: UI components, KPI row, shopper deals
│   ├── test_demand_optimizer.py            # 15 tests: Datasets, schemas, floor, optimization
│   ├── test_pricing_engine.py              # 16 tests: Cost floors, GAAP accounting identities
│   ├── test_performance_analysis.py        # 15 tests: Sensitivity & performance metrics
│   └── test_data_generator.py              # 9 tests: Catalog schemas & reproducibility
├── .streamlit/
│   └── config.toml                         # Streamlit light theme configuration
├── app.py                                  # Dashboard root launcher entrypoint
├── requirements.txt                        # Python dependencies
└── README.md                               # Comprehensive MVP documentation
```

---

## 5. Setup Instructions

FreshPrice AI requires Python 3.10+ (tested on Python 3.12.5).

```bash
# Clone the repository
git clone https://github.com/thilagars4767-ux/freshprice-ai.git
cd freshprice

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1       # On Windows PowerShell
# source .venv/bin/activate      # On macOS/Linux

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 6. Dependencies

FreshPrice AI relies on standard, production-ready scientific Python packages specified in `requirements.txt`:

| Package | Minimum Version | Purpose |
| :--- | :--- | :--- |
| `streamlit` | `1.32.0+` | Interactive web dashboard and UI components |
| `pandas` | `2.0.0+` | Tabular data manipulation and timeseries indexing |
| `numpy` | `1.24.0+` | Numerical arrays and random seed RNG generators |
| `plotly` | `5.18.0+` | Interactive SVG/WebGL charts and hover tooltips |
| `pytest` | `7.4.0+` | Unit testing and automated invariant verification |
| `matplotlib`| `3.7.0+` | Backend chart rendering utilities |

---

## 7. How to Launch the Dashboard

Launch the interactive Streamlit dashboard:

```bash
# Via launcher script:
py -m streamlit run app.py

# Or directly:
py -m streamlit run src/dashboard.py
```

The application will start locally at `http://localhost:8501`.

### Dashboard Portals & Controls:
- **Application View**: Toggle between **🏢 Store Operations Dashboard** and **🛍️ Today's Fresh Deals (Shopper Portal)**.
- **Simulation Duration**: 7 to 60 days (default: `30` days).
- **Random Seed**: Integer seed for reproducible stochastic demand (default: `42`).
- **Markdown Strategy**: Toggle between **Demand-Aware Optimized Markdown** and **Graduated Rule Markdown**.
- **Discount Sliders**: Urgent clearance discount (0%–80%, default `40%`) and Near-expiry discount (0%–80%, default `20%`).
- **Threshold Sliders**: Days-to-expiry clearance triggers (default: `1` day and `2` days).
- **Minimum Gross Margin Floor**: Target minimum gross profit margin percentage (0%–40%, default `10%`).
- **Shopper Demand Sensitivity ($\gamma$)**: Response multiplier (`0.25x`, `0.50x`, `0.75x`, `1.00x`, `1.25x`, default `1.00x`).

---

## 8. How to Run Tests

Execute the full automated test suite containing 112 unit tests across all 7 test suites:

```bash
# Run all tests with verbose output:
py -m pytest tests -v

# Run individual test modules:
py -m pytest tests/test_category_optimizer.py -v
py -m pytest tests/test_store_simulator.py -v
py -m pytest tests/test_dashboard.py -v
py -m pytest tests/test_demand_optimizer.py -v
py -m pytest tests/test_pricing_engine.py -v
py -m pytest tests/test_performance_analysis.py -v
py -m pytest tests/test_data_generator.py -v
```

All 112 tests execute in approximately 22 seconds and assert 100% pass rate.

---

## 9. Product Catalog & Synthetic Data

The catalog models **20 perishable grocery products** across 4 categories (5 SKUs per category) with realistic unit economics in Indian Rupees (₹).

| ID | Product Name | Category | Shelf Life | Unit Cost (₹) | Regular Price (₹) | Regular Margin % | Base Daily Demand | Sensitivity ($\eta$) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `PROD-01` | Toned Fresh Milk | Dairy | 3 days | ₹52.00 | ₹60.00 | 13.33% | 35.0 units | 1.40 |
| `PROD-02` | Full Cream Fresh Milk | Dairy | 3 days | ₹64.00 | ₹74.00 | 13.51% | 30.0 units | 1.30 |
| `PROD-03` | Fresh Curd / Dahi | Dairy | 6 days | ₹32.00 | ₹42.00 | 23.81% | 25.0 units | 1.50 |
| `PROD-04` | Malai Paneer | Dairy | 5 days | ₹82.00 | ₹105.00 | 21.90% | 18.0 units | 1.60 |
| `PROD-05` | Spiced Buttermilk | Dairy | 4 days | ₹13.00 | ₹18.00 | 27.78% | 28.0 units | 1.50 |
| `PROD-06` | White Sandwich Bread | Bakery | 4 days | ₹30.00 | ₹40.00 | 25.00% | 30.0 units | 1.70 |
| `PROD-07` | Whole Wheat Atta Bread | Bakery | 4 days | ₹38.00 | ₹50.00 | 24.00% | 22.0 units | 1.60 |
| `PROD-08` | Ladi Pav | Bakery | 3 days | ₹20.00 | ₹28.00 | 28.57% | 35.0 units | 1.80 |
| `PROD-09` | Brioche Burger Buns | Bakery | 4 days | ₹30.00 | ₹42.00 | 28.57% | 18.0 units | 1.70 |
| `PROD-10` | Garlic Herb Baguette | Bakery | 3 days | ₹50.00 | ₹68.00 | 26.47% | 12.0 units | 1.90 |
| `PROD-11` | Royal Gala Apples | Fruits | 8 days | ₹130.00 | ₹180.00 | 27.78% | 22.0 units | 1.50 |
| `PROD-12` | Robusta Bananas | Fruits | 4 days | ₹40.00 | ₹58.00 | 31.03% | 35.0 units | 1.80 |
| `PROD-13` | Nagpur Mandarin Oranges| Fruits | 7 days | ₹62.00 | ₹88.00 | 29.55% | 20.0 units | 1.60 |
| `PROD-14` | Green Seedless Grapes | Fruits | 5 days | ₹50.00 | ₹72.00 | 30.56% | 18.0 units | 1.80 |
| `PROD-15` | Semi-Ripe Papaya | Fruits | 4 days | ₹28.00 | ₹42.00 | 33.33% | 20.0 units | 1.70 |
| `PROD-16` | Hybrid Tomatoes | Vegetables | 5 days | ₹24.00 | ₹36.00 | 33.33% | 40.0 units | 1.60 |
| `PROD-17` | Fresh White Cauliflower | Vegetables | 5 days | ₹24.00 | ₹36.00 | 33.33% | 25.0 units | 1.70 |
| `PROD-18` | Baby Spinach (Palak) | Vegetables | 3 days | ₹14.00 | ₹22.00 | 36.36% | 32.0 units | 1.90 |
| `PROD-19` | Green Capsicum | Vegetables | 5 days | ₹30.00 | ₹45.00 | 33.33% | 18.0 units | 1.60 |
| `PROD-20` | Button Mushrooms | Vegetables | 4 days | ₹40.00 | ₹58.00 | 31.03% | 16.0 units | 1.80 |

> **Disclaimer**: All transaction numbers, sales counts, batches, and prices are **synthetic data** generated algorithmically for hackathon evaluation and benchmarking.

---

## 10. Data Schemas & Column Descriptions

The project generates and maintains 5 standardized benchmark datasets in `data/`:

### 1. `data/products.csv` (20 rows)
- `product_id`: Unique identifier (`PROD-01` to `PROD-20`).
- `product_name`: Perishable SKU commercial name.
- `category`: Department classification (`dairy`, `bakery`, `fruits`, `vegetables`).
- `regular_price`: Standard base retail price in INR (₹).
- `unit_cost`: Wholesale acquisition cost per unit in INR (₹).
- `base_daily_demand`: Average daily un-promoted customer demand (units).
- `price_sensitivity`: Price elasticity response factor ($\eta \ge 1.0$).
- `shelf_life_days`: Total physical lifespan from production to expiry (3 to 8 days).

### 2. `data/historical_product_demand.csv` (7,300 rows: 365 days × 20 products)
- `date`: Calendar date (`YYYY-MM-DD`).
- `product_id` & `product_name` & `category`: SKU metadata.
- `regular_price` & `actual_price`: Sticker price vs. dynamic selling price (₹).
- `discount_pct`: Markdown discount applied (0.0 to 0.40).
- `unit_cost`: Acquisition cost per unit (₹).
- `opening_stock`: Inventory available at store opening.
- `units_received`: New replenishment batch arriving that morning.
- `units_available`: $\text{opening\_stock} + \text{units\_received}$.
- `units_sold`: Units purchased by customers (modeled with 0.1-unit precision).
- `units_wasted`: Units expired and discarded that morning.
- `closing_stock`: $\text{units\_available} - \text{units\_sold}$.
- `days_to_expiry`: Remaining shelf life of active stock.
- `weekday`: Day of week name (`Monday` to `Sunday`).

### 3. `data/product_price_history.csv` (7,300 rows)
- `date`, `product_id`, `product_name`: SKU tracking.
- `regular_price`, `discount_pct`, `actual_price`, `unit_cost`: Price trajectory.
- `reason_for_price_change`: Audit explanation (`Regular Price`, `Near-Expiry Clearance`, `Urgent Clearance`).

### 4. `data/inventory_batch_history.csv` (3,953 batches)
- `batch_id`: Unique batch identifier (`BATCH-PROD-XX-YYYYMMDD-N`).
- `product_id`: Associated SKU ID.
- `manufacture_date` & `expiry_date`: Life interval.
- `shelf_life_days`: Duration in days.
- `quantity_received`: Initial delivery quantity.
- `quantity_remaining`: Units remaining un-depleted.
- `unit_cost`: Unit cost incurred for the batch.

### 5. `data/daily_store_history.csv` (365 rows)
- `date`: Date of business operations.
- `units_sold`: Aggregate store-wide units sold.
- `units_wasted`: Aggregate physical units spoiled.
- `revenue`: Gross store sales in INR ($\sum P_{\text{actual}} \times Q_{\text{sold}}$).
- `cogs`: Store cost of goods sold in INR ($\sum C \times Q_{\text{sold}}$).
- `gross_profit`: Revenue minus COGS.
- `ending_inventory`: Store-wide closing stock across all 20 SKUs.

---

## 11. Inventory Batch Assumptions

1. **Discrete Batches**: Inventory is received and stored in discrete batches. Each batch is uniquely identified by `batch_id` and tracked with an arrival day and an absolute expiration day.
2. **Morning Delivery**: Batches arrive at the beginning of the simulation day before customer opening.
3. **Physical Non-Negativity**: Inventory quantities can never drop below zero ($S \ge 0$). Overselling is physically impossible.
4. **Feasibility Bound**: Units sold on any day can never exceed physically available unexpired stock ($Q_{\text{sold}} \le Q_{\text{avail}}$).

---

## 12. Shelf-Life Assumptions

- Catalog shelf lives vary from **3 days** (ultra-perishable fresh milk, ladi pav, spinach) to **8 days** (royal gala apples).
- **Shelf-Life-Aware Guardrails**: To prevent absurd pricing behavior where a product with a 3-day shelf life is marked down 20% on day 1 (when it is 67% fresh), FreshPrice AI dynamically caps markdown windows:
  $$\text{effective\_t2} = \min\left(\text{config\_t2},\ \max(1,\ \text{shelf\_life\_days} - 2)\right)$$
  $$\text{effective\_t1} = \min\left(\text{config\_t1},\ \text{effective\_t2}\right)$$
  For a 3-day product, markdown is restricted strictly to the final day before expiry ($t=1$), guaranteeing no premature discounting.

---

## 13. Replenishment Rules

- Each SKU has a predetermined replenishment schedule:
  - Delivery Interval: Every 1, 2, or 3 days depending on product velocity.
  - Delivery Batch Size: Configured to support average demand while maintaining a lean safety buffer.
- Initial Inventory (Day 1): Seeded with an initial batch arriving on Day 1 with full shelf life.
- Pre-Scheduled Arrivals: The entire arrival schedule for the 30-day run is pre-generated before policy evaluation, ensuring Policy A and Policy B receive **identical replenishment quantities on identical days**.

---

## 14. First-Expiry-First-Out (FEFO) Depletion Behavior

FreshPrice AI enforces strict **First-Expiry-First-Out (FEFO)** fulfillment:
1. When customer demand arrives, the simulator inspects all available unexpired batches for that SKU.
2. Batches are sorted in ascending order of `expiry_day`.
3. Sales deplete the batch nearest to expiration first. If that batch is exhausted, sales spill over to the next batch.
4. If a batch reaches its `expiry_day` without being depleted, it cannot be sold and is permanently removed during morning inventory audit.

---

## 15. The 4-Step Simulation Pipeline (Stock → Demand → Pricing → Evaluation)

The simulation executes daily operations through four sequential, mathematically verified phases:

```text
Each Day t (Day 1 to Day N):
 1. STOCK & BATCHES   --> Scheduled deliveries arrive. Expired stock (current_day >= expiry_day)
                           is purged as waste. Unexpired stock is queued in FEFO order.
 2. DEMAND INFLOW     --> Stochastic customer footfall (Poisson) arrives with price elasticity
                           and near-expiry urgency response. Bounded by unexpired stock.
 3. PRICING DECISION  --> Selects policy (Fixed vs Graduated Rule vs Optimizer). Applies shelf-life
                           thresholds and clamps selling price to margin floor P >= C / (1 - m).
 4. EVALUATION & GAAP --> Records sales, revenue, COGS, and GAAP Gross Profit. Deducts waste cost
                           to track operational Net Contribution. Verifies inventory conservation.
```

> **💡 Single-Slide Hackathon Summary**:  
> FreshPrice AI synchronizes daily inventory arrivals, queues perishable stock in FEFO order, stimulates clearance demand as expiry nears while strictly clamping selling prices above wholesale cost/margin floors, and reconciles GAAP Gross Profit with real operational waste reduction.

---

## 16. Demand Equation, Sensitivity Multiplier & Modeling Precision

### Customer Demand Response Model
Customer demand responds dynamically to price discounts and urgency:

$$Q_{\text{sim}} = \min\left(S_{\text{avail}},\ \text{round}\left(D_{\text{base}} \times [1 + \gamma \cdot \eta \cdot d] \times f_{\text{urgency}}(T),\ 1\right)\right)$$

Where:
- $D_{\text{base}}$: Pre-generated baseline daily demand drawn from a Poisson distribution around `avg_daily_demand`.
- $\gamma \in [0.25, 1.25]$: **Shopper Discount-Response Multiplier** controlling elasticity response strength (default `1.00`).
- $\eta$: Product price sensitivity ($\eta \ge 1.0$).
- $d$: Applied markdown discount percentage ($0.0 \le d \le 0.80$).
- $f_{\text{urgency}}(T)$: Markdown display effect ($1.15$ if discounted, $0.85$ if near expiry without discount, $1.0$ otherwise).
- Zero sales after expiry: If $T_{\text{left}} < 1$, selling price is voided and demand fulfillment is $0$.

### Fractional Units & Modeling Precision
The simulator models physical sales and inventory at **0.1-unit precision**:
- **Why Fractional Values Occur**: Applying continuous price-elasticity multipliers ($1 + \gamma \cdot \eta \cdot d$) to discrete footfall produces continuous expected daily demand.
- **Produce-by-Weight Realism**: In grocery retail, perishable produce (apples, bananas, tomatoes, cauliflower) is sold by weight (kg/fractional units).
- **Mathematical Integrity**: Fractional unit tracking prevents artificial quantization noise and ensures physical inventory conservation holds to within 0.0001 units across all 30 days.

---

## 17. Random Seed & Reproducibility

- The simulation is completely deterministic when initialized with a given random seed (default: `seed = 42`).
- To guarantee perfect comparability, the random seed initializes a unified random number generator that draws the full 30-day baseline demand schedule **before** running either policy.
- Both Policy A and Policy B evaluate against the exact same customer arrival shocks.
- Changing the seed produces different, fully reproducible weather/traffic realizations.

---

## 18. Policy A: Fixed-Price Baseline

The Fixed-Price policy models conventional supermarket operations:
- Every product is always sold at its full `regular_price` ($d = 0\%$).
- No promotional markdowns are ever offered, regardless of how close a batch is to expiration.
- Healthy stock sells at full margin, but expiring batches invariably spoil when customer demand fluctuates downwards.
- Unsold items that cross `current_day >= expiry_day` are purged as physical waste loss.

---

## 19. Policy B: Markdown Policies (Graduated Rule & Demand-Aware)

FreshPrice AI offers two markdown strategies:

### 1. Graduated Rule Markdown
- **Near-Expiry Markdown**: When remaining days to expiry $T_{\text{left}} \le 2$ days, applies a `20%` discount.
- **Urgent Clearance**: When remaining days to expiry $T_{\text{left}} \le 1$ day, applies a `40%` discount.
- Shelf-life awareness automatically constrains short-life SKUs to appropriate clearance windows.

### 2. Demand-Aware Optimized Markdown
- Evaluates discrete candidate markdowns: $d \in \{0\%, 5\%, 10\%, 15\%, 20\%, 30\%, 40\%\}$.
- Predicts expected sales $\hat{Q}(d)$ and expected waste $\hat{W}(d)$.
- Optimizes net profit: $\max_d \hat{Q}(d)(P(d) - C) - \hat{W}(d)(C + \text{Fee}_{\text{disposal}})$.
- **Zero-Discount Safeguard**: If stock will naturally clear at regular price ($S \le T_{\text{left}} \times \hat{D}_0$), discount is set to **0%**, completely preventing unnecessary margin sacrifice.

---

## 20. Category-Specific Markdown Optimizer

Implemented in [`src/category_optimizer.py`](file:///c:/freshprice/src/category_optimizer.py), the Category Optimizer tailors markdown schedules per department:
1. **Dynamic Category Discovery**: Discovers catalog departments (`dairy`, `bakery`, `fruits`, `vegetables`).
2. **Candidate Schedule Evaluation**: Evaluates 4 candidate clearance policies per department:
   - Conservative: $\le 1\text{d}: 20\% \mid \le 2\text{d}: 10\%$
   - Moderate: $\le 1\text{d}: 30\% \mid \le 2\text{d}: 15\%$
   - Aggressive: $\le 1\text{d}: 40\% \mid \le 2\text{d}: 20\%$
   - Deep Salvage: $\le 1\text{d}: 50\% \mid \le 2\text{d}: 25\%$
3. **Multi-Seed Robustness**: Evaluates candidates across multiple seeds (`[42, 101, 2026]`) with matched starting inventory and demand shocks.
4. **Primary Objective**: Selects the schedule that maximizes **Average Net Contribution after Waste Cost**.
5. **Reported Metrics**: Revenue, Gross Profit, Gross Margin %, Waste Units, Waste Cost, Sell-Through %, Ending Inventory, and comparison vs. fixed baseline.

---

## 21. Shopper Discount-Response Sensitivity Analysis

To evaluate model robustness against shopper behavior, FreshPrice AI provides a sensitivity multiplier control ($\gamma$):
- **Formula**: Incremental discount uplift is scaled by $\gamma$:
  $$\text{adjusted\_multiplier} = 1.0 + \gamma \times (\text{raw\_price\_multiplier} - 1.0)$$
- **Settings**: $\gamma \in [0.25, 0.50, 0.75, 1.00, 1.25]$.
- **Invariance**: When $d = 0\%$, incremental uplift is $0$, meaning baseline demand is 100% preserved.
- **Directional Behavior**: At $\gamma = 0.50$ (half-strength response), clearance velocity slows down, revealing the degree of waste increase under inelastic consumer response.
- **Academic Disclaimer**: This is an econometric sensitivity experiment evaluating model robustness; it is not a measured empirical shopper panel.

---

## 22. Shopper-Facing Portal: "Today's Fresh Deals"

FreshPrice AI provides a prominent top-level navigation toggle between **Store Operations** and **Today's Fresh Deals**:
- **Smart Active-Day Selector**: Dynamically identifies days with active clearance deals (e.g. Day 3 has 10 deals, Day 5 has 8 deals, Day 11 has 11 deals) and defaults to the first day with deals so the page opens immediately with active offers.
- **Strict Quality & Integrity Constraints**:
  - Excludes expired items ($\text{days\_to\_expiry} \ge 1$ strictly enforced).
  - Excludes non-discounted items ($d > 0\%$ only; regular-price items never appear).
  - Excludes out-of-stock items ($Q_{\text{avail}} = \text{sold} + \text{ending} > 0$).
  - Respects minimum margin floor ($P_{\text{selling}} \ge P_{\text{min}}$).
- **Deal Card Attributes**: Product Name, Category badge, Struck-through Regular Price, Clearance Selling Price, Discount % badge, Days Remaining urgency text, Freshness indicator (Within 24h / 48h), and Available Units in stock.
- **Professional Empty State**: Displays an informative notice when viewing a day without clearance items (e.g. Day 1 or Day 30), explaining that items appear when inventory approaches expiry thresholds and suggesting active deal days.
- **Fixed-Price Policy Clarification**: If the store is operating under Fixed-Price Policy, clearly notifies that no clearance discounts are offered and explains how to switch to Markdown Pricing.
- **No-Checkout Notice**: Clearly labeled with an unobtrusive disclaimer: *"Simulation demo: all prices, inventory levels, and clearance offers are generated from synthetic data. No real transactions are available."*

---

## 23. Minimum Gross Margin Floor Calculation

Retailers must never sell inventory below wholesale cost or sacrifice required minimum gross margins. FreshPrice AI enforces a hard mathematical price floor:

$$P_{\text{min}} = \frac{C}{1 - m_{\text{min}}}$$

Where:
- $C$: Wholesale acquisition unit cost.
- $m_{\text{min}}$: Minimum gross margin percentage floor (e.g., $10\% = 0.10$).
- If $m_{\text{min}} = 0\%$, $P_{\text{min}} = C$ (strict wholesale cost floor).

If a configured markdown discount would push the selling price below $P_{\text{min}}$, the discount is automatically clamped:

$$P_{\text{selling}} = \max\left(P_{\text{regular}} \times (1 - d),\ P_{\text{min}}\right)$$
$$d_{\text{actual}} = 1.0 - \frac{P_{\text{selling}}}{P_{\text{regular}}}$$

When this occurs, the markdown event logs `margin_floor_limited = True` with both `requested_discount_pct` and `actual_discount_pct` recorded for complete operational transparency. Configurations with $m_{\text{min}} \ge 100\%$ raise a `ValueError`.

---

## 24. Revenue & Accounting Formulas (GAAP Compliant)

All operational and financial metrics strictly obey standard Generally Accepted Accounting Principles (GAAP):

$$\text{Total Received} = \text{Initial Inventory} + \sum \text{Delivered Batches}$$
$$\text{Total Sold} = \sum_{t=1}^{N} \sum_{i=1}^{20} Q_{i, t}$$
$$\text{Total Wasted} = \sum_{t=1}^{N} \sum_{i=1}^{20} W_{i, t}$$
$$\text{Total Revenue} = \sum_{t=1}^{N} \sum_{i=1}^{20} Q_{i, t} \times P_{i, t}$$
$$\text{Cost of Goods Sold (COGS)} = \sum_{t=1}^{N} \sum_{i=1}^{20} Q_{i, t} \times C_{i}$$
$$\text{Gross Profit (Gross Margin INR)} = \text{Revenue} - \text{COGS}$$
$$\text{Gross Margin Percentage} = \frac{\text{Gross Profit}}{\text{Revenue}} \times 100\%$$
$$\text{Sell-Through Rate} = \frac{\text{Total Sold}}{\text{Total Received}} \times 100\%$$
$$\text{Waste Rate} = \frac{\text{Total Wasted}}{\text{Total Received}} \times 100\%$$
$$\text{Physical Inventory Conservation}: \quad S_{\text{ending}} = \text{Total Received} - \text{Total Sold} - \text{Total Wasted}$$

---

## 25. Waste Cost Treatment: GAAP vs. Net Contribution

In accordance with retail accounting standards:
1. **GAAP Accounting**: Under standard retail GAAP, unsold inventory spoilage is an asset write-off that is not deducted from top-line product Revenue or product Gross Profit. COGS reflects only units that were actually sold to customers.
2. **Operational Net Contribution after Waste Cost**: From an operational and managerial accounting standpoint, discarded inventory represents real cash loss. FreshPrice AI explicitly calculates:
   $$\text{Total Waste Cost} = \sum_{i=1}^{20} W_i \times C_i$$
   $$\text{Net Contribution after Waste Cost} = \text{Gross Profit} - \text{Total Waste Cost}$$

The dashboard displays both figures side by side with an explicit accounting disclosure, ensuring complete financial transparency without conflating Gross Profit and Net Contribution.

---

## 26. Fair-Comparison Methodology

To ensure scientifically and methodologically valid comparison between Policy A (Fixed) and Policy B (Markdown):
1. **Identical Starting Stock**: Initial inventory on Day 1 is identical for both runs down to the single unit.
2. **Identical Replenishment Schedule**: Scheduled batch deliveries arrive on the exact same days with identical batch sizes and expiration dates.
3. **Identical Customer Inflows**: Daily customer demand draws are pre-computed using a single master random seed before policy evaluation begins.
4. **Isolated Policy Logic**: The only variable differing between Policy A and Policy B is the price determination logic applied at store opening.

---

## 27. Historical Price Analysis (365 Days)

The interactive dashboard (Section 4) features an advanced retail price analytics explorer backed by `data/product_price_history.csv` and `data/historical_product_demand.csv`:
- **Regular vs. Actual Selling Price**: Interactive Plotly timeseries showing dynamic promotional price drops in FreshPrice Red (`#E23744`) against regular base price in Slate (`#718096`).
- **Promotional Discount History**: Daily discount percentage bar chart tracking markdown frequency.
- **Demand Velocity vs. Available Stock**: Daily units sold plotted against physical inventory depth to inspect stock depletion curves.
- **Product & Date-Range Filtering**: Allows filtering across any of the 20 SKUs and custom historical date ranges.

---

## 28. Known Limitations

1. **Single-Store Scope**: The current simulator models a single retail store environment without inter-store cross-dock transfers or regional distribution center dynamics.
2. **Deterministic Arrival Fulfillment**: Scheduled batch arrivals are assumed to arrive on time with 100% vendor fulfillment (no supplier stock-outs or transport delays).
3. **Independent Product Demand**: Demand elasticity is modeled at the product level. Cross-product substitution (e.g., customers switching from Toned Milk to Full Cream Milk when discounted) is not explicitly modeled.
4. **Synthetic Data**: Historical data and simulation records are generated algorithmically for demonstration and hackathon evaluation; they do not represent real proprietary supermarket sales audits.

---

## 29. Example Experiment Workflow

Here is how an evaluator can run a complete end-to-end experiment from the command line:

### Step 1: Run Baseline Simulator (Default Settings)
```powershell
py src/store_simulator.py --days 30 --seed 42
```
*Output: Simulates 30 days under seed 42. Displays the 14-metric GAAP policy comparison table showing waste reduction from ~1,617 units to 0 units.*

### Step 2: Run Demand-Aware Optimization with 15% Margin Floor
```powershell
py src/store_simulator.py --days 30 --seed 42 --policy-mode demand_aware --min-margin 15.0
```
*Output: Enforces the 15% gross margin floor, preventing deep clearance discounting on low-margin products.*

### Step 3: Launch Streamlit Dashboard
```powershell
py -m streamlit run app.py
```
*Open `http://localhost:8501` to interactively adjust markdown sliders, view the Executive KPI row, explore Category Clearance Optimizer, test Shopper Response Sensitivity, and view Today's Fresh Deals storefront.*

### Step 4: Run Automated Verification Tests
```powershell
py -m pytest tests -v
```
*Executes all 112 tests verifying 100% pass rate.*

---

## License

Developed for the **NEXAI 2026 Hackathon (PS 4.1 Track 4: Grocery Retail)**. Released under the MIT License.
