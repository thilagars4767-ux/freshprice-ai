# FreshPrice AI

FreshPrice is an intelligent dynamic pricing and markdown optimization system designed for grocery retail. It algorithmically reduces perishable food waste while safeguarding retail margins.

> **Disclaimer**: All datasets generated, simulated, and utilized in this project are **synthetic** and generated algorithmically for hackathon, simulation, and academic demonstration purposes. All monetary amounts are in **INR (Indian Rupees - ₹)**. Simulation results illustrate algorithmic dynamics and do not represent actual supermarket sales or financial guarantees.

---

## Project Structure

```text
freshprice/
├── data/
│   ├── .gitkeep
│   └── synthetic_grocery_inventory.csv   # Phase 1: 120 Indian grocery batches (INR)
├── src/
│   ├── __init__.py
│   ├── data_generator.py                 # Phase 1: Synthetic Indian grocery generator
│   └── pricing_engine.py                 # Phase 2: Dynamic pricing engine & simulator
├── tests/
│   ├── __init__.py
│   ├── test_data_generator.py            # Phase 1: Test suite (9 tests)
│   └── test_pricing_engine.py            # Phase 2: Test suite (15 tests)
├── app.py                                # Application entrypoint
├── requirements.txt                      # Project dependencies
├── README.md                             # Documentation & instructions
├── DEV_LOG.md                            # Development progress log
└── .gitignore                            # Git ignore configuration
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

### 2. Discount Recommendation Policy

Discounts are determined based on inventory coverage and shelf-life urgency:

1. **Inventory Coverage Ratio**:
   $$\text{Coverage Ratio} = \frac{\text{initial\_stock}}{\max(\text{daily\_demand} \times \text{days\_to\_expiry}, 0.001)}$$
   - If $\text{Coverage Ratio} \le 1.0$: Baseline demand clears the stock before expiry. No discount is required unless expiry is imminent (1–2 days remaining).
   - If $\text{Coverage Ratio} > 1.0$: Surplus inventory will spoil. The required clearance discount is:
     $$d_{\text{clearance}} = \frac{\text{Coverage Ratio} - 1}{|E_d|}$$

2. **Expiry Urgency Component**:
   Discounts scale upwards as expiry approaches:
   - $\le 1$ day remaining: 20% baseline urgency discount.
   - $\le 2$ days remaining: 10% baseline urgency discount.
   - $\le 3$ days remaining: 5% baseline urgency discount.

3. **Strict Price Floor & Profitability Constraints**:
   - **Cost Floor**: Selling price is **never recommended below unit cost** ($P_{\text{recommended}} \ge \text{unit\_cost}$).
   - **Max Discount Cap**: Configurable ceiling (default $d_{\max} = 40\%$).
   - **Profitability Guarantee**: The engine checks whether candidate markdowns produce higher net profit than the baseline under identical inventory and cost assumptions. If a discount would reduce net profit, the engine **retains the regular price** and reports that limitation.

### 3. Financial & Retail Accounting Identities

All batch-level and aggregate financial metrics reconcile mathematically according to standard retail accounting:

$$\text{Revenue} = \text{Units Sold} \times \text{Selling Price}$$

$$\text{COGS} = \text{Units Sold} \times \text{Unit Cost}$$

$$\text{Gross Profit on Sold Units} = \text{Revenue} - \text{COGS} = \text{Units Sold} \times (\text{Selling Price} - \text{Unit Cost})$$

$$\text{Waste Loss (Spoilage Cost)} = \text{Unsold Units} \times \text{Unit Cost}$$

$$\text{Total Initial Inventory Cost} = \text{Initial Stock} \times \text{Unit Cost} = \text{COGS} + \text{Waste Loss}$$

$$\text{Net Retail Profit} = \text{Revenue} - \text{Total Initial Inventory Cost} = \text{Gross Profit} - \text{Waste Loss}$$

$$\text{Waste Rate (\%)} = \frac{\text{Total Unsold Units}}{\text{Total Initial Stock}} \times 100\%$$

### 4. Accounting Audit: Why Batches with Positive Selling Margins Show Negative Net Profit

A critical retail insight verified during auditing:
- A batch can have a **positive gross margin** ($\text{selling\_price} > \text{unit\_cost}$) on the units sold, but still yield a **negative net profit** for the batch overall.
- **Root Cause**: When a batch has substantial surplus stock that cannot be sold within its remaining shelf life, the expired stock must be written off as **Waste Loss**. If $\text{Waste Loss} > \text{Gross Profit}$, then:
  $$\text{Net Retail Profit} = \text{Gross Profit} - \text{Waste Loss} < 0$$
- **Example (Toned Fresh Milk - PROD-0101)**:
  - 114 litres purchased at ₹52.95/litre (Total Cost: ₹6,036.30).
  - 89.84 litres sold at ₹58.90/litre (Selling margin: +₹5.95/litre).
  - **Gross Profit**: ₹534.55 (Positive margin on sold units).
  - **Waste Loss**: 24.16 expired litres × ₹52.95 = ₹1,279.27.
  - **Net Retail Profit**: ₹534.55 − ₹1,279.27 = **-₹744.72**.
  - **Fixed Baseline Comparison**: Under fixed pricing (no discount), 28.80 litres expired, resulting in a **Net Profit of -₹753.90**.
  - **Verdict**: Dynamic pricing mitigated the loss by **+₹9.18** and saved 4.64 litres of milk from waste, but could not eliminate the underlying loss caused by severe initial overstocking.

### 5. Deterministic Continuous Expectation (Fractional Units)

In this deterministic simulation, daily demand represents a continuous average rate. Consequently, `units_sold` and `unsold_units` are continuous expected values (e.g. 20.10 loaves, 89.84 litres) rather than discrete stochastic integer draws. This maintains exact mathematical reproducibility while preserving analytical precision.

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

Run the pricing engine to evaluate the dataset and print the full comparison report:

```bash
py src/pricing_engine.py
```

Optional CLI arguments:
```bash
# Run with custom max discount cap (e.g. 35%) and export comparison summary to CSV:
py src/pricing_engine.py --max-discount 0.35 --output-summary data/pricing_comparison_summary.csv
```

### 4. Running the Complete Test Suite

Run pytest across all Phase 1 and Phase 2 test suites (24 tests):

```bash
py -m pytest tests -v
```
