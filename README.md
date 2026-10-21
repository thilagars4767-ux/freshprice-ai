# FreshPrice AI

FreshPrice is a pricing intelligence and markdown optimization system designed to minimize grocery waste and maximize retail revenue.

> **Disclaimer**: All datasets generated and utilized in this project are **synthetic** and generated algorithmically for hackathon, simulation, and academic demonstration purposes. All prices and costs are expressed in **INR (Indian Rupees - ₹)** and represent synthetic illustrative figures, not real proprietary supermarket or audited market quotations.

---

## Project Structure

```text
freshprice/
├── data/
│   ├── .gitkeep
│   └── synthetic_grocery_inventory.csv   # Generated synthetic inventory (INR)
├── src/
│   ├── __init__.py
│   └── data_generator.py                 # Indian grocery dataset generator
├── tests/
│   ├── __init__.py
│   └── test_data_generator.py            # Test suite for Phase 1
├── app.py                                # Application entrypoint
├── requirements.txt                      # Project dependencies
├── README.md                             # Documentation & instructions
├── DEV_LOG.md                            # Development progress log
└── .gitignore                            # Git ignore configuration
```

---

## Phase 1: Synthetic Indian Grocery Dataset

The dataset simulates realistic inventory for an Indian grocery store across five major categories: `dairy`, `bakery`, `fruits`, `vegetables`, and `packaged food`.

### Schema Definition

| Column | Type | Description | Illustrative INR (₹) Scale / Range |
| :--- | :--- | :--- | :--- |
| `product_id` | `str` | Unique batch identifier | `PROD-0001`, `PROD-0002`, ... |
| `product_name` | `str` | Product catalog name | e.g., `Toned Fresh Milk`, `Royal Gala Apples`, `Table Potatoes (Aloo)` |
| `category` | `str` | Grocery section | `dairy`, `bakery`, `fruits`, `vegetables`, `packaged food` |
| `unit` | `str` | Quantity/selling unit | `per litre`, `per kilogram`, `per 500 g pack`, `per loaf`, `per head`, etc. |
| `initial_stock` | `int` | Available units in current batch | 10–150 units |
| `unit_cost` | `float` | Acquisition cost per unit (INR ₹) | Product-specific (e.g. ₹18–₹23 for potatoes, ₹50–₹54 for toned milk) |
| `regular_price` | `float` | Standard retail price (INR ₹) | Strictly > `unit_cost` based on product-specific markup |
| `days_to_expiry` | `int` | Shelf-life remaining | Perishables (2–14 days), Packaged foods (60–180 days) |
| `daily_demand` | `float` | Baseline daily customer demand | 5.0–80.0 units/day |
| `price_elasticity` | `float` | Price elasticity of demand | Negative (-0.45 to -2.30) |

### Illustrative Product Unit Pricing (INR ₹)

| Product | Category | Selling Unit | Illustrative Cost (₹) | Illustrative Retail Price (₹) | Shelf Life |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Toned Fresh Milk | `dairy` | per litre | ₹50.00 – ₹54.00 | ₹56.00 – ₹64.00 | 2–4 days |
| Full Cream Fresh Milk | `dairy` | per litre | ₹62.00 – ₹66.00 | ₹68.00 – ₹76.00 | 2–4 days |
| Fresh Curd / Dahi | `dairy` | per 500 g pack | ₹30.00 – ₹35.00 | ₹36.00 – ₹45.00 | 5–9 days |
| Malai Paneer | `dairy` | per 200 g pack | ₹78.00 – ₹86.00 | ₹95.00 – ₹110.00 | 4–8 days |
| White Sandwich Bread | `bakery` | per loaf | ₹28.00 – ₹32.00 | ₹35.00 – ₹45.00 | 3–5 days |
| Ladi Pav | `bakery` | per 6-piece pack | ₹18.00 – ₹23.00 | ₹25.00 – ₹34.00 | 2–4 days |
| Royal Gala Apples | `fruits` | per kilogram | ₹120.00 – ₹145.00 | ₹160.00 – ₹210.00 | 7–14 days |
| Cavendish Bananas | `fruits` | per dozen | ₹38.00 – ₹46.00 | ₹52.00 – ₹70.00 | 3–6 days |
| Table Potatoes (Aloo) | `vegetables` | per kilogram | ₹18.00 – ₹23.00 | ₹25.00 – ₹35.00 | 14–25 days |
| Red Cooking Onions | `vegetables` | per kilogram | ₹26.00 – ₹33.00 | ₹35.00 – ₹48.00 | 12–21 days |
| Fresh White Cauliflower | `vegetables` | per head | ₹22.00 – ₹30.00 | ₹32.00 – ₹48.00 | 4–7 days |
| Royal Daawat Basmati Rice | `packaged food` | per kilogram | ₹95.00 – ₹115.00 | ₹120.00 – ₹155.00 | 90–180 days |
| Durum Wheat Spaghetti | `packaged food` | per 500 g pack | ₹68.00 – ₹82.00 | ₹88.00 – ₹115.00 | 90–180 days |
| Whole Wheat Chakki Atta | `packaged food` | per 5 kg bag | ₹210.00 – ₹235.00 | ₹250.00 – ₹295.00 | 60–120 days |

---

## Setup & Execution

### 1. Installation

Ensure Python 3.10+ is available:

```bash
# Optional: create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1    # On Windows
# source .venv/bin/activate   # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

*(Note: On Windows systems with the Python launcher, you can use `py` in place of `python`.)*

### 2. Generating the Synthetic Dataset

Generate the default 120 Indian grocery records with seed 42:

```bash
py src/data_generator.py
```

Or customize record count, seed, and destination:

```bash
py src/data_generator.py --records 150 --seed 42 --output data/synthetic_grocery_inventory.csv
```

### 3. Running Tests

Run pytest to verify dataset validity, explicit units, INR pricing integrity, reproducibility, and CLI execution:

```bash
py -m pytest tests -v
```
