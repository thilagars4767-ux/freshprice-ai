# FreshPrice AI

FreshPrice is an intelligent dynamic pricing and markdown optimization system designed for grocery retail. It algorithmically reduces perishable food waste while safeguarding retail margins.

> **Disclaimer**: All datasets generated, simulated, and utilized in this project are **synthetic** and generated algorithmically for hackathon, simulation, and academic demonstration purposes. All monetary amounts are in **INR (Indian Rupees - ₹)**. Simulation results illustrate algorithmic dynamics and do not represent actual supermarket sales or financial guarantees.

---

## Project Structure

```text
freshprice/
├── data/
│   ├── .gitkeep
│   ├── synthetic_grocery_inventory.csv     # Phase 1: 120 Indian grocery batches (INR)
│   ├── category_performance_summary.csv    # Phase 3: Category-level comparison
│   ├── discount_sensitivity_summary.csv    # Phase 3: Discount cap sensitivity (10-35%)
│   └── elasticity_sensitivity_summary.csv  # Phase 3: Elasticity sensitivity (0.5-2.0)
├── reports/
│   ├── phase3_performance_report.md        # Phase 3: Full evaluation report
│   ├── category_waste_and_profit.png       # Phase 3: Category waste & profit charts
│   └── sensitivity_analysis.png            # Phase 3: Sensitivity curve charts
├── src/
│   ├── __init__.py
│   ├── data_generator.py                   # Phase 1: Synthetic Indian grocery generator
│   ├── pricing_engine.py                   # Phase 2: Dynamic pricing engine & simulator
│   └── performance_analysis.py             # Phase 3: Evaluation & sensitivity module
├── tests/
│   ├── __init__.py
│   ├── test_data_generator.py              # Phase 1: Test suite (9 tests)
│   ├── test_pricing_engine.py              # Phase 2: Test suite (15 tests)
│   └── test_performance_analysis.py        # Phase 3: Test suite (9 tests)
├── app.py                                  # Application entrypoint
├── requirements.txt                        # Project dependencies
├── README.md                               # Documentation & instructions
├── DEV_LOG.md                              # Development progress log
└── .gitignore                              # Git ignore configuration
```

---

## Phase 1: Synthetic Indian Grocery Dataset

The dataset models an Indian grocery store with 120 product-batch records across five realistic categories: `dairy`, `bakery`, `fruits`, `vegetables`, and `packaged food`.

### Schema Definition

| Column | Type | Description | Illustrative INR (₹) Scale / Range |
| :--- | :--- | :--- | :--- |
| `product_id` | `str` | Unique batch identifier | `PROD-0001`, `PROD-0002`, ... |
| `product_name` | `str` | Product catalog item | e.g., `Toned Fresh Milk`, `Royal Gala Apples`, `Table Potatoes (Aloo)` |
| `category` | `str` | Grocery department | `dairy`, `bakery`, `fruits`, `vegetables`, `packaged food` |
| `unit` | `str` | Quantity/selling unit | `per litre`, `per kilogram`, `per 500 g pack`, `per loaf`, `per head`, etc. |
| `initial_stock` | `int` | Available units in batch | 10–150 units |
| `unit_cost` | `float` | Acquisition cost per unit (INR ₹) | Product-specific (₹12–₹345) |
| `regular_price` | `float` | Standard retail price (INR ₹) | Strictly > `unit_cost` based on product markup |
| `days_to_expiry` | `int` | Remaining shelf life | Perishables (2–14 days), Packaged foods (60–180 days) |
| `daily_demand` | `float` | Baseline daily customer demand | 5.0–80.0 units/day |
| `price_elasticity` | `float` | Price elasticity of demand | Negative (-0.45 to -2.30) |

---

## Phase 2: Dynamic Markdown Pricing Engine & Accounting Audit

The pricing engine compares a **Fixed-Price Baseline** (standard retail pricing without discounts) against a **Dynamic Markdown Strategy** that optimizes price markdowns to clear excess perishable stock before expiration.

### 1. Demand Response Equation (Price Elasticity of Demand)

The engine models customer demand stimulation using standard economic price elasticity:

$$\Delta Q = E_d \times \frac{\Delta P}{P_0}$$

Given discount fraction $d = \frac{P_0 - P_{\text{dyn}}}{P_0} \ge 0$, the price change fraction is $\frac{\Delta P}{P_0} = -d$. Substituting:

$$Q_{\text{dyn}} = Q_0 \times (1 - E_d \times d) = Q_0 \times (1 + |E_d| \times d)$$

Where:
- $Q_0$ = Baseline daily demand at regular price.
- $E_d$ = Price elasticity of demand ($E_d < 0$).
- $d$ = Discount fraction ($0 \le d \le d_{\max}$).
- $Q_{\text{dyn}}$ = Stimulated daily demand.

### 2. Financial & Retail Accounting Identities

All batch-level and aggregate financial metrics reconcile mathematically according to standard retail accounting:

$$\text{Revenue} = \text{Units Sold} \times \text{Selling Price}$$

$$\text{COGS} = \text{Units Sold} \times \text{Unit Cost}$$

$$\text{Gross Profit on Sold Units} = \text{Revenue} - \text{COGS} = \text{Units Sold} \times (\text{Selling Price} - \text{Unit Cost})$$

$$\text{Waste Loss (Spoilage Cost)} = \text{Unsold Units} \times \text{Unit Cost}$$

$$\text{Total Initial Inventory Cost} = \text{Initial Stock} \times \text{Unit Cost} = \text{COGS} + \text{Waste Loss}$$

$$\text{Net Retail Profit} = \text{Revenue} - \text{Total Initial Inventory Cost} = \text{Gross Profit} - \text{Waste Loss}$$

$$\text{Waste Rate (\%)} = \frac{\text{Total Unsold Units}}{\text{Total Initial Stock}} \times 100\%$$

---

## Phase 3: Performance Evaluation & Sensitivity Analysis

Phase 3 provides comprehensive benchmarking, sensitivity analysis, and empirical simulation findings across product categories, discount ceilings, and consumer price elasticity scenarios.

### 1. Feature 1: Category-Level Performance Evaluation

| Category | Batches | Initial Stock | Fixed Waste | Dynamic Waste | Waste Red. (%) | Fixed Net Profit (INR) | Dynamic Net Profit (INR) | Profit Gain (INR) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Bakery** | 24 | 821 | 9.60 | 1.90 | **80.21%** | ₹10,753.76 | ₹10,869.88 | **+₹116.12** |
| **Dairy** | 24 | 1,163 | 51.00 | 36.52 | **28.39%** | ₹13,664.84 | ₹13,720.33 | **+₹55.49** |
| **Fruits** | 24 | 999 | 0.00 | 0.00 | 0.00% | ₹33,417.11 | ₹33,417.11 | +₹0.00 |
| **Vegetables** | 24 | 1,544 | 0.00 | 0.00 | 0.00% | ₹18,679.70 | ₹18,679.70 | +₹0.00 |
| **Packaged Food** | 24 | 1,094 | 0.00 | 0.00 | 0.00% | ₹30,804.32 | ₹30,804.32 | +₹0.00 |

- **Highest Waste Reduction (%)**: **Bakery** at **80.21%**, due to fast turnover and responsive price elasticity.
- **Highest Volume Saved**: **Dairy** with **14.48 units** rescued from spoilage.
- **Zero-Waste Categories**: In categories where baseline demand naturally clears stock before expiry, the pricing engine applies a 0% discount, strictly protecting regular prices and avoiding unnecessary margin loss.

### 2. Feature 2: Maximum-Discount Sensitivity (10% to 35%)

| Discount Setting | Units Sold | Unsold (Waste) | Waste Rate (%) | Waste Red. vs Fixed (%) | Total Revenue (INR) | Net Retail Profit (INR) | Profit Gain vs Fixed (INR) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Fixed (0%)** | 5,560.40 | 60.60 | 1.08% | 0.00% | ₹463,182.46 | ₹107,319.73 | +0.00 |
| **10% Cap** | 5,579.40 | 41.60 | 0.74% | 31.35% | ₹463,332.53 | ₹107,469.80 | +₹150.07 |
| **20% Cap** | 5,581.92 | 39.08 | 0.70% | 35.51% | ₹463,353.99 | ₹107,491.26 | +₹171.53 |
| **30% Cap** | 5,582.58 | 38.42 | 0.68% | **36.60%** | ₹463,354.07 | ₹107,491.34 | **+₹171.61** |
| **35% Cap** | 5,582.58 | 38.42 | 0.68% | **36.60%** | ₹463,354.07 | ₹107,491.34 | **+₹171.61** |

- **Optimal Setting**: Under the synthetic catalog assumptions, **30%** achieves the maximum possible benefit.
- **Plateau Behavior**: Relaxing the cap to 35% yields identical results because wholesale cost floor boundaries ($P \ge \text{unit\_cost}$) and calculated clearance needs never exceed 22.6% for any batch in the current inventory.

### 3. Feature 3: Price-Elasticity Sensitivity (0.5 to 2.0)

| Assumed Elasticity (|Ed|) | Scenario Label | Waste Rate (%) | Waste Red. vs Fixed (%) | Net Retail Profit (INR) | Profit Gain vs Fixed (INR) | Strategy Behavior |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **0.5** | Inelastic | 1.08% | 0.00% | ₹107,319.73 | +₹0.00 | Profitability rule holds regular price (markdowns avoided) |
| **1.0** | Unitary Elastic | 1.08% | 0.00% | ₹107,319.73 | +₹0.00 | Regular price held (demand increase cannot offset cost margin) |
| **1.5** | Elastic | 0.25% | **77.00%** | ₹107,976.65 | **+₹656.92** | Dynamic markdowns actively clear excess inventory |
| **2.0** | Highly Elastic | 0.08% | **92.48%** | ₹108,701.84 | **+₹1,382.11** | Near-total elimination of perishable food waste |

- **Inelastic Scenarios ($|E_d| \le 1.0$)**: When demand does not respond sufficiently to price cuts, discounting destroys cash margin without clearing enough stock. FreshPrice AI protects the retailer by **holding regular prices**.
- **Elastic Scenarios ($|E_d| \ge 1.5$)**: Markdown pricing achieves dramatic waste reduction (up to 92.48%) while simultaneously driving significant profit growth.

---

## Setup & Execution

### 1. Installation

Ensure Python 3.10+ is available:

```bash
# Optional: create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1    # On Windows
# source .venv/bin/activate   # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

*(Note: On Windows systems with the Python launcher, you can use `py` in place of `python`.)*

### 2. Running Phase 1 (Data Generator)

Generate 120 synthetic Indian grocery records with seed 42:

```bash
py src/data_generator.py
```

### 3. Running Phase 2 (Pricing Engine Simulation)

Run the pricing engine simulation and print the comparison report:

```bash
py src/pricing_engine.py
```

### 4. Running Phase 3 (Performance Evaluation & Sensitivity Analysis)

Execute the full Phase 3 performance evaluation, sensitivity analysis, and chart generation:

```bash
py src/performance_analysis.py
```

Generated outputs:
- `data/category_performance_summary.csv`
- `data/discount_sensitivity_summary.csv`
- `data/elasticity_sensitivity_summary.csv`
- `reports/phase3_performance_report.md`
- `reports/category_waste_and_profit.png`
- `reports/sensitivity_analysis.png`

### 5. Running the Complete Test Suite

Run pytest across all Phase 1, Phase 2, and Phase 3 test suites (33 tests):

```bash
py -m pytest tests -v
```
