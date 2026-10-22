# FreshPrice AI — Markdown Before Waste: Near-Expiry Pricing

**NEXAI 2026 Hackathon — Problem Statement 4.1 (Track 4: Grocery Retail)**  
Repository: [https://github.com/thilagars4767-ux/freshprice-ai](https://github.com/thilagars4767-ux/freshprice-ai)

FreshPrice AI simulates a dynamic 30-day grocery store operations environment modeling 20 perishable products to benchmark two distinct retail pricing strategies:
1. **Fixed-Price Policy**: The standard retail baseline that maintains full base selling price until products expire.
2. **Markdown Policy**: An intelligent near-expiry markdown mechanism that applies graduated price markdowns as shelf life nears expiration, bound by a wholesale cost floor.

> **Academic & Hackathon Disclaimer**: All inventory counts, product parameters, batch arrivals, costs, prices, and demand curves are **synthetic illustrative data** generated algorithmically for hackathon demonstration. Values are denominated in **INR (Indian Rupees - ₹)**. They do not represent actual commercial supermarket audits or financial commitments.

---

## 1. The Problem

Perishable grocery retail suffers from structural food waste. Products such as fresh milk, artisanal bread, curd, paneer, and ripe produce have strict shelf lives (2 to 8 days). When retailers maintain static regular prices up until expiration:
- Customers avoid older batches when fresher stock is available at the same price.
- Unsold items cross their expiry date and become an outright loss (**spoilage waste**).
- Retailers incur double financial damage: zero revenue on unsold units, plus the total sunk acquisition cost.

**The Solution**: Intelligently markdown products before expiration to stimulate clearance demand while strictly respecting a wholesale unit cost floor ($P \ge \text{unit\_cost}$), converting would-be trash into cash revenue.

---

## 2. Simulation Workflow & Operations

The simulation loop executes daily operations for Days 1 through 30:

```text
Each Day t (Day 1 to Day 30):
 1. Inventory Receiving   --> Add scheduled batch arrivals for Day t into active store inventory.
 2. Morning Expiry Check  --> Identify batches where current_day >= expiry_day.
                              Mark as expired waste and remove immediately before store opens.
 3. Price Determination   --> Fixed: charges regular base price.
                              Markdown: inspects minimum days until expiry across active stock.
                              Applies graduated discount if within threshold, capped at unit cost.
 4. Demand Generation     --> Evaluates base customer traffic + price elasticity response + expiry effect.
 5. FEFO Fulfillment      --> Depletes unexpired stock using First-Expiry-First-Out (FEFO) batch priority.
 6. Accounting Tracking   --> Records units sold, revenue, COGS, gross margin, and wasted units.
 7. Historical Logging    --> Appends to per-product daily ledger and markdown event history.
```

---

## 3. Core Assumptions & Mathematical Formulations

### A. Catalog & Perishability Scope
- **Product Count**: Exactly 20 perishable grocery products across 4 staple departments (5 Dairy, 5 Bakery, 5 Fruits, 5 Vegetables).
- **Shelf Lives**: Realistic perishability ranges from 3 to 8 days (e.g. 3 days for Toned Milk, 4 days for Sandwich Bread, 8 days for Apples).
- **Currency**: Indian Rupees (INR - ₹).
- **Pricing Integrity**: Regular base selling prices are strictly greater than wholesale unit acquisition costs ($P_{\text{base}} > \text{unit\_cost}$).

### B. Batch Arrival & Expiry Rules
- **Arrival Frequency**: Products arrive periodically every 2 to 4 days in pre-set batch order quantities (28 to 85 units).
- **Expiry Day Convention**: A batch arriving on day $t_{\text{arr}}$ with shelf life $L$ has $\text{expiry\_day} = t_{\text{arr}} + L$.
- **No Sales After Expiry**: On any day $t \ge \text{expiry\_day}$, days until expiry is $\le 0$. Any remaining units in the batch are declared expired and discarded during morning inspection before opening. **Products are never sold on or after their expiry day**.

### C. Demand Model & Price Response
Consumer shopping behavior combines baseline store footfall, price elasticity of demand, and clearance display visibility:

$$D_{i, t} = \text{round}\left( D_{0, i, t} \times \left(1.0 + \eta_i \times d_{i, t}\right) \times f_{\text{expiry}}(T_{\text{min}}) \right)$$

Where:
- $D_{0, i, t}$ = Baseline stochastic customer demand drawn from a Poisson distribution ($\lambda_{0, i}$) controlled by the random seed.
- $\eta_i$ = Product price sensitivity (elasticity factor between 1.3 and 1.9).
- $d_{i, t} = \frac{P_{\text{base}} - P_{\text{selling}}}{P_{\text{base}}}$ = Discount fraction.
- $f_{\text{expiry}}$ = Expiry display factor:
  - Under markdown ($d > 0$): $1.15$ (promotional clearance signage attracts bargain shoppers).
  - Under fixed pricing ($d = 0$) with 1–2 days left: $0.85$ (shopper reluctance to pay full price for near-expiry items).

### D. Shelf-Life-Aware Markdown Policy & Precedence Rules
To avoid premature discounting on short-shelf-life staples (e.g. discounting a 3-day milk SKU on Day 2 when 67% of its shelf life remains), markdown eligibility is calibrated dynamically based on catalog shelf life:

$$\text{effective\_threshold\_2} = \min\left(\text{configured\_threshold\_2},\ \max(1,\ \text{shelf\_life\_days} - 2)\right)$$
$$\text{effective\_threshold\_1} = \min\left(\text{configured\_threshold\_1},\ \text{effective\_threshold\_2}\right)$$

**Precedence & Operational Rules**:
1. **Urgent Clearance Precedence**: If $\text{min\_days\_to\_expiry} \le \text{effective\_threshold\_1}$ and $d_1 > 0$, the Urgent Clearance discount is applied (default 40%).
2. **Near-Expiry Markdown**: If urgent clearance does not apply, but $\text{min\_days\_to\_expiry} \le \text{effective\_threshold\_2}$ and $d_2 > 0$, the Near-Expiry Markdown is applied (default 20%).
3. **Single Discount Rule**: Exactly **one discount** applies per product per day; discounts never stack, compound, or combine.
4. **Wholesale Cost Floor**: Selling prices strictly respect the wholesale unit acquisition cost:
   $$P_{\text{selling}} = \max\left(\text{unit\_cost},\ P_{\text{base}} \times (1 - d)\right)$$
   Retailers never sell below acquisition cost, preventing cash losses on clearance sales.

### E. Seed Reproducibility
- Both policies run with the **exact same random seed** (default `42`).
- Baseline demand draws and shipment schedules are pre-generated so Fixed and Markdown policies face **100% identical starting conditions and customer traffic**.
- Results are deterministic and reproducible.

---

## 4. Standard Metric Definitions

All metrics adhere to standard retail and GAAP accounting:

1. **Total Received**: Sum of all units received across all batches over the 30 days.
2. **Units Sold**: Total quantity purchased by customers over 30 days.
3. **Units Wasted**: Total expired quantity removed from inventory.
4. **Waste Rate (%)**:
   $$\text{Waste Rate} = \frac{\text{Units Wasted}}{\text{Total Received}} \times 100\%$$
5. **Waste Reduction (%)**:
   $$\text{Waste Reduction} = \frac{\text{Fixed Waste} - \text{Markdown Waste}}{\text{Fixed Waste}} \times 100\%$$
6. **Total Revenue**: Sum of $\text{Selling Price} \times \text{Units Sold}$.
7. **Cost of Goods Sold (COGS)**: Sum of $\text{Unit Cost} \times \text{Units Sold}$.
8. **Gross Margin (INR)**:
   $$\text{Gross Margin} = \text{Revenue} - \text{COGS}$$
9. **Gross Margin (%)**:
   $$\text{Gross Margin \%} = \frac{\text{Gross Margin}}{\text{Revenue}} \times 100\%$$

*Note: In accordance with retail accounting principles, Gross Margin measures sales profitability ($\text{Revenue} - \text{COGS}$). Waste loss ($\text{Units Wasted} \times \text{Unit Cost}$) is accounted for separately and not subtracted from COGS.*

---

## 5. 30-Day Benchmark Simulation Results (Seed 42)

| Metric | Fixed-Price Policy | Markdown Policy | Difference |
| :--- | :---: | :---: | :---: |
| **Initial Inventory Received** | 14,895.0 units | 14,895.0 units | 0.0 units (Identical) |
| **Units Sold** | 12,601.3 units | 14,774.6 units | **+2,173.3 units** |
| **Units Wasted (Expired)** | 1,617.0 units | 0.0 units | **-1,617.0 units** |
| **Waste Rate (%)** | **10.86%** | **0.00%** | **-10.86% (100% reduction)** |
| **Total Store Revenue** | ₹671,151.00 | ₹726,303.80 | **+₹55,152.80 (+8.2%)** |
| **Cost of Goods Sold (COGS)** | ₹494,303.50 | ₹569,747.20 | +₹75,443.70 |
| **Gross Margin (INR)** | ₹176,847.50 | ₹156,556.60 | -₹20,290.90 |
| **Gross Margin (%)** | 26.35% | 21.56% | -4.79% |
| **Markdown Events Triggered** | 0 events | 126 events | +126 events |

*Insight*: By incorporating shelf-life-aware eligibility, unnecessary promotions on 3-day products on Day 2 are prevented, reducing markdown events from 162 down to 126 while eliminating spoilage waste on Seed 42 and preserving revenue expansion.

---

## 6. Multi-Seed Evaluation & Model Limitations

### Multi-Seed Sensitivity (Seeds: 42, 1, 7, 13, 21, 55, 99, 123, 777, 999)
- **Fixed-Price Baseline**: Mean waste of **1,549.35 units** (10.40% waste rate), mean gross margin of **₹176,846.73**.
- **Revised Markdown Policy**: Mean waste of **6.57 units** (0.04% waste rate), mean gross margin of **₹157,852.27**.
- **Mean Waste Reduction**: **99.54%** (saving 1,542.8 units of food on average).
- **Zero-Waste Occurrence**: 4 out of 10 seeds achieve 0.0 waste; 6 out of 10 seeds exhibit realistic non-zero waste (0.1 to 25.8 units) due to stochastic low-demand traffic days.

### Limitations of the Synthetic Simulation Model
1. **Synthetic Demand Draws**: Consumer footfall and shopping volume are generated via synthetic Poisson and lognormal random variables. They reflect retail distribution models but do not constitute empirical in-store POS audit data.
2. **Constant Price Elasticity**: Elasticities ($\eta = 1.3\text{--}1.9$) are modeled linearly per SKU; cross-price cannibalization across substitutable categories is not modeled.
3. **Fixed Delivery Schedules**: Deliveries arrive on fixed cadences (2–4 days) rather than continuous automated inventory reordering (Min-Max/s,S) policies.
4. **Continuous Quantity Fulfillment**: Inventory is tracked with 1 decimal place rather than whole customer pack sizes, which allows continuous fluid clearance.
5. **Evaluator Guidance**: These results should be interpreted as a comparative simulator benchmark demonstrating markdown mechanism design rather than real-world commercial performance guarantees.

---

## 7. Setup & Execution

### Installation

```bash
# Optional virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1    # On Windows
# source .venv/bin/activate   # On macOS/Linux

# Install dependencies (pandas, numpy, pytest, matplotlib, streamlit, plotly)
pip install -r requirements.txt
```

### Running the Streamlit Dashboard

Launch the single-page interactive dashboard:

```bash
py -m streamlit run app.py
# Or:
py -m streamlit run src/dashboard.py
```
Open `http://localhost:8501` to adjust thresholds, change the random seed, and inspect the per-product markdown history.

### Running the Store Simulator CLI

Run the headless 30-day simulation and export all CSV files:

```bash
py src/store_simulator.py --days 30 --seed 42
```

Generated MVP CSV deliverables:
- `data/mvp_products.csv` (20 perishable products definitions)
- `data/daily_simulation_history.csv` (1,200 daily product records)
- `data/policy_comparison_summary.csv` (reconciled comparison metrics)
- `data/markdown_events_history.csv` (126 chronological markdown audit events)

### Running the Test Suite

Execute pytest across all 78 unit tests:

```bash
py -m pytest tests -v
```

---

## 7. Project Structure

```text
freshprice/
├── data/
│   ├── mvp_products.csv                    # 20 perishable product definitions
│   ├── daily_simulation_history.csv        # 30-day per-product operational history
│   ├── policy_comparison_summary.csv       # Reconciled Fixed vs Markdown metrics
│   └── markdown_events_history.csv         # Chronological markdown triggers
├── src/
│   ├── __init__.py
│   ├── store_simulator.py                  # Core 30-day daily store simulator (PS 4.1)
│   ├── dashboard.py                        # Single-page Streamlit interactive dashboard
│   ├── data_generator.py                   # Catalog templates and data utilities
│   ├── pricing_engine.py                   # Dynamic pricing core
│   └── performance_analysis.py             # Analytical evaluation module
├── tests/
│   ├── __init__.py
│   ├── test_store_simulator.py             # 15 tests: PS 4.1 store simulator requirements
│   ├── test_dashboard.py                   # 4 tests: Dashboard visualizations & integration
│   ├── test_data_generator.py              # 9 tests: Catalog and seed integrity
│   ├── test_pricing_engine.py              # 16 tests: Pricing constraints and accounting
│   └── test_performance_analysis.py        # 15 tests: Sensitivity & performance metrics
├── app.py                                  # Streamlit application entrypoint
├── requirements.txt                        # Project dependencies
├── README.md                               # Project documentation & assumptions
├── DEV_LOG.md                              # Development log
└── .gitignore                              # Git ignore rules
```
