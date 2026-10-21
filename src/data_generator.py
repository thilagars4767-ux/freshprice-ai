"""Synthetic Grocery Inventory Dataset Generator for FreshPrice AI.

NOTE ON CURRENCY & DATA ORIGIN:
All monetary values (unit_cost, regular_price) are expressed in INR (Indian Rupees - ₹).
All prices, demand figures, and stock levels are synthetic, illustrative estimates
designed for hackathon development, simulation, and academic demonstration.
They do NOT represent actual supermarket quotations or audited store data.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# Target output directory and default filename
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_FILE = DEFAULT_DATA_DIR / "synthetic_grocery_inventory.csv"

# Comprehensive Indian Grocery Product Catalog
# Each entry defines product name, selling unit, realistic INR wholesale cost range,
# retail markup range, shelf-life (expiry in days), stock, baseline daily demand, and price elasticity.
PRODUCT_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "dairy": [
        {
            "name": "Toned Fresh Milk",
            "unit": "per litre",
            "cost_range": (50.0, 54.0),
            "markup_range": (0.10, 0.18),
            "expiry_range": (2, 4),
            "stock_range": (40, 120),
            "demand_range": (25.0, 60.0),
            "elasticity_range": (-1.30, -0.90),
        },
        {
            "name": "Full Cream Fresh Milk",
            "unit": "per litre",
            "cost_range": (62.0, 66.0),
            "markup_range": (0.10, 0.16),
            "expiry_range": (2, 4),
            "stock_range": (30, 100),
            "demand_range": (20.0, 50.0),
            "elasticity_range": (-1.20, -0.80),
        },
        {
            "name": "Fresh Curd / Dahi",
            "unit": "per 500 g pack",
            "cost_range": (30.0, 35.0),
            "markup_range": (0.20, 0.32),
            "expiry_range": (5, 9),
            "stock_range": (25, 70),
            "demand_range": (15.0, 40.0),
            "elasticity_range": (-1.50, -1.00),
        },
        {
            "name": "Malai Paneer",
            "unit": "per 200 g pack",
            "cost_range": (78.0, 86.0),
            "markup_range": (0.20, 0.30),
            "expiry_range": (4, 8),
            "stock_range": (20, 60),
            "demand_range": (10.0, 30.0),
            "elasticity_range": (-1.60, -1.10),
        },
        {
            "name": "Salted Table Butter",
            "unit": "per 500 g pack",
            "cost_range": (235.0, 252.0),
            "markup_range": (0.12, 0.18),
            "expiry_range": (30, 90),
            "stock_range": (15, 45),
            "demand_range": (8.0, 20.0),
            "elasticity_range": (-1.30, -0.85),
        },
        {
            "name": "Pure Cow Ghee",
            "unit": "per 500 ml jar",
            "cost_range": (315.0, 345.0),
            "markup_range": (0.15, 0.22),
            "expiry_range": (90, 180),
            "stock_range": (10, 35),
            "demand_range": (5.0, 15.0),
            "elasticity_range": (-1.20, -0.80),
        },
        {
            "name": "Processed Cheese Cubes",
            "unit": "per 200 g pack",
            "cost_range": (110.0, 125.0),
            "markup_range": (0.20, 0.30),
            "expiry_range": (30, 90),
            "stock_range": (15, 50),
            "demand_range": (8.0, 22.0),
            "elasticity_range": (-1.50, -1.00),
        },
        {
            "name": "Greek Style Yogurt",
            "unit": "per 500 g pack",
            "cost_range": (75.0, 88.0),
            "markup_range": (0.22, 0.35),
            "expiry_range": (7, 14),
            "stock_range": (10, 35),
            "demand_range": (5.0, 18.0),
            "elasticity_range": (-1.80, -1.20),
        },
        {
            "name": "Spiced Buttermilk (Chaas)",
            "unit": "per 500 ml pouch",
            "cost_range": (12.0, 15.0),
            "markup_range": (0.25, 0.35),
            "expiry_range": (3, 6),
            "stock_range": (30, 80),
            "demand_range": (20.0, 50.0),
            "elasticity_range": (-1.60, -1.10),
        },
        {
            "name": "Fresh Dairy Cream",
            "unit": "per 250 ml pack",
            "cost_range": (56.0, 65.0),
            "markup_range": (0.18, 0.28),
            "expiry_range": (10, 25),
            "stock_range": (12, 35),
            "demand_range": (6.0, 18.0),
            "elasticity_range": (-1.40, -0.95),
        },
    ],
    "bakery": [
        {
            "name": "White Sandwich Bread",
            "unit": "per loaf",
            "cost_range": (28.0, 32.0),
            "markup_range": (0.25, 0.40),
            "expiry_range": (3, 5),
            "stock_range": (25, 60),
            "demand_range": (20.0, 45.0),
            "elasticity_range": (-1.80, -1.20),
        },
        {
            "name": "Whole Wheat Atta Bread",
            "unit": "per loaf",
            "cost_range": (36.0, 42.0),
            "markup_range": (0.25, 0.36),
            "expiry_range": (3, 5),
            "stock_range": (20, 50),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-1.70, -1.15),
        },
        {
            "name": "Multigrain Brown Bread",
            "unit": "per loaf",
            "cost_range": (45.0, 52.0),
            "markup_range": (0.28, 0.40),
            "expiry_range": (3, 5),
            "stock_range": (15, 40),
            "demand_range": (10.0, 25.0),
            "elasticity_range": (-1.90, -1.30),
        },
        {
            "name": "Ladi Pav",
            "unit": "per 6-piece pack",
            "cost_range": (18.0, 23.0),
            "markup_range": (0.30, 0.45),
            "expiry_range": (2, 4),
            "stock_range": (30, 75),
            "demand_range": (25.0, 60.0),
            "elasticity_range": (-2.10, -1.40),
        },
        {
            "name": "Brioche Burger Buns",
            "unit": "per 4-piece pack",
            "cost_range": (28.0, 34.0),
            "markup_range": (0.25, 0.38),
            "expiry_range": (3, 5),
            "stock_range": (15, 40),
            "demand_range": (10.0, 25.0),
            "elasticity_range": (-1.90, -1.30),
        },
        {
            "name": "Crispy Wheat Rusks (Toast)",
            "unit": "per 300 g pack",
            "cost_range": (35.0, 42.0),
            "markup_range": (0.25, 0.38),
            "expiry_range": (30, 60),
            "stock_range": (20, 50),
            "demand_range": (12.0, 30.0),
            "elasticity_range": (-1.40, -0.95),
        },
        {
            "name": "Fruit Cake Slice Pack",
            "unit": "per 250 g pack",
            "cost_range": (52.0, 62.0),
            "markup_range": (0.28, 0.42),
            "expiry_range": (14, 30),
            "stock_range": (15, 40),
            "demand_range": (8.0, 20.0),
            "elasticity_range": (-1.70, -1.15),
        },
        {
            "name": "Butter Croissant",
            "unit": "per 2-piece pack",
            "cost_range": (65.0, 78.0),
            "markup_range": (0.35, 0.50),
            "expiry_range": (2, 3),
            "stock_range": (10, 30),
            "demand_range": (6.0, 18.0),
            "elasticity_range": (-2.30, -1.50),
        },
        {
            "name": "Garlic Herb Baguette",
            "unit": "per loaf",
            "cost_range": (48.0, 58.0),
            "markup_range": (0.30, 0.45),
            "expiry_range": (2, 3),
            "stock_range": (10, 28),
            "demand_range": (6.0, 16.0),
            "elasticity_range": (-2.10, -1.40),
        },
        {
            "name": "Sweet Cinnamon Swirl Buns",
            "unit": "per 2-piece pack",
            "cost_range": (40.0, 50.0),
            "markup_range": (0.30, 0.45),
            "expiry_range": (2, 4),
            "stock_range": (12, 32),
            "demand_range": (8.0, 20.0),
            "elasticity_range": (-2.00, -1.35),
        },
    ],
    "fruits": [
        {
            "name": "Royal Gala Apples",
            "unit": "per kilogram",
            "cost_range": (120.0, 145.0),
            "markup_range": (0.30, 0.45),
            "expiry_range": (7, 14),
            "stock_range": (25, 70),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-1.90, -1.25),
        },
        {
            "name": "Shimla Red Delicious Apples",
            "unit": "per kilogram",
            "cost_range": (105.0, 130.0),
            "markup_range": (0.30, 0.45),
            "expiry_range": (7, 14),
            "stock_range": (30, 80),
            "demand_range": (18.0, 40.0),
            "elasticity_range": (-1.80, -1.20),
        },
        {
            "name": "Robusta Cavendish Bananas",
            "unit": "per dozen",
            "cost_range": (38.0, 46.0),
            "markup_range": (0.35, 0.55),
            "expiry_range": (3, 6),
            "stock_range": (35, 90),
            "demand_range": (25.0, 60.0),
            "elasticity_range": (-2.10, -1.35),
        },
        {
            "name": "Nagpur Mandarin Oranges",
            "unit": "per kilogram",
            "cost_range": (55.0, 70.0),
            "markup_range": (0.35, 0.50),
            "expiry_range": (5, 10),
            "stock_range": (25, 65),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-1.90, -1.25),
        },
        {
            "name": "Ruby Pomegranate (Anar)",
            "unit": "per kilogram",
            "cost_range": (135.0, 165.0),
            "markup_range": (0.30, 0.45),
            "expiry_range": (7, 12),
            "stock_range": (20, 55),
            "demand_range": (10.0, 25.0),
            "elasticity_range": (-1.70, -1.15),
        },
        {
            "name": "Striped Watermelon",
            "unit": "per piece",
            "cost_range": (42.0, 55.0),
            "markup_range": (0.40, 0.60),
            "expiry_range": (5, 9),
            "stock_range": (20, 50),
            "demand_range": (12.0, 30.0),
            "elasticity_range": (-2.20, -1.45),
        },
        {
            "name": "Green Seedless Grapes (Nashik)",
            "unit": "per 500 g pack",
            "cost_range": (45.0, 58.0),
            "markup_range": (0.35, 0.50),
            "expiry_range": (4, 7),
            "stock_range": (20, 55),
            "demand_range": (12.0, 30.0),
            "elasticity_range": (-2.10, -1.40),
        },
        {
            "name": "Semi-Ripe Papaya",
            "unit": "per kilogram",
            "cost_range": (26.0, 34.0),
            "markup_range": (0.40, 0.60),
            "expiry_range": (3, 6),
            "stock_range": (25, 60),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-2.00, -1.35),
        },
        {
            "name": "Ratnagiri Alphonso Mangoes",
            "unit": "per kilogram",
            "cost_range": (210.0, 260.0),
            "markup_range": (0.30, 0.45),
            "expiry_range": (4, 8),
            "stock_range": (15, 50),
            "demand_range": (10.0, 30.0),
            "elasticity_range": (-1.80, -1.20),
        },
        {
            "name": "Mosambi (Sweet Lime)",
            "unit": "per kilogram",
            "cost_range": (52.0, 66.0),
            "markup_range": (0.35, 0.50),
            "expiry_range": (6, 11),
            "stock_range": (20, 55),
            "demand_range": (12.0, 28.0),
            "elasticity_range": (-1.80, -1.20),
        },
    ],
    "vegetables": [
        {
            "name": "Table Potatoes (Aloo)",
            "unit": "per kilogram",
            "cost_range": (18.0, 23.0),
            "markup_range": (0.35, 0.55),
            "expiry_range": (14, 25),
            "stock_range": (60, 150),
            "demand_range": (35.0, 80.0),
            "elasticity_range": (-1.20, -0.80),
        },
        {
            "name": "Red Cooking Onions (Pyaz)",
            "unit": "per kilogram",
            "cost_range": (26.0, 33.0),
            "markup_range": (0.35, 0.50),
            "expiry_range": (12, 21),
            "stock_range": (50, 140),
            "demand_range": (30.0, 75.0),
            "elasticity_range": (-1.20, -0.80),
        },
        {
            "name": "Hybrid Tomatoes (Tamatar)",
            "unit": "per kilogram",
            "cost_range": (22.0, 30.0),
            "markup_range": (0.40, 0.60),
            "expiry_range": (4, 8),
            "stock_range": (40, 110),
            "demand_range": (25.0, 65.0),
            "elasticity_range": (-1.80, -1.20),
        },
        {
            "name": "Fresh White Cauliflower",
            "unit": "per head",
            "cost_range": (22.0, 30.0),
            "markup_range": (0.45, 0.65),
            "expiry_range": (4, 7),
            "stock_range": (25, 70),
            "demand_range": (15.0, 40.0),
            "elasticity_range": (-2.00, -1.30),
        },
        {
            "name": "Green Cabbage (Patta Gobhi)",
            "unit": "per head",
            "cost_range": (16.0, 22.0),
            "markup_range": (0.45, 0.65),
            "expiry_range": (5, 9),
            "stock_range": (25, 65),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-1.90, -1.25),
        },
        {
            "name": "Baby Spinach (Palak)",
            "unit": "per 250 g bunch",
            "cost_range": (12.0, 16.0),
            "markup_range": (0.45, 0.70),
            "expiry_range": (2, 4),
            "stock_range": (30, 80),
            "demand_range": (20.0, 50.0),
            "elasticity_range": (-2.20, -1.45),
        },
        {
            "name": "Green Capsicum (Shimla Mirch)",
            "unit": "per 500 g pack",
            "cost_range": (28.0, 36.0),
            "markup_range": (0.40, 0.55),
            "expiry_range": (4, 8),
            "stock_range": (20, 55),
            "demand_range": (12.0, 30.0),
            "elasticity_range": (-1.80, -1.20),
        },
        {
            "name": "Red Carrots (Gajar)",
            "unit": "per kilogram",
            "cost_range": (30.0, 40.0),
            "markup_range": (0.35, 0.55),
            "expiry_range": (7, 14),
            "stock_range": (25, 65),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-1.60, -1.05),
        },
        {
            "name": "English Cucumber",
            "unit": "per 500 g pack",
            "cost_range": (18.0, 25.0),
            "markup_range": (0.40, 0.60),
            "expiry_range": (4, 7),
            "stock_range": (25, 60),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-2.00, -1.30),
        },
        {
            "name": "Fresh Button Mushrooms",
            "unit": "per 200 g pack",
            "cost_range": (38.0, 48.0),
            "markup_range": (0.30, 0.45),
            "expiry_range": (3, 6),
            "stock_range": (15, 45),
            "demand_range": (10.0, 25.0),
            "elasticity_range": (-2.00, -1.35),
        },
    ],
    "packaged food": [
        {
            "name": "Royal Daawat Basmati Rice",
            "unit": "per kilogram",
            "cost_range": (95.0, 115.0),
            "markup_range": (0.25, 0.38),
            "expiry_range": (90, 180),
            "stock_range": (30, 90),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-1.30, -0.85),
        },
        {
            "name": "Premium Sona Masoori Rice",
            "unit": "per kilogram",
            "cost_range": (48.0, 56.0),
            "markup_range": (0.22, 0.32),
            "expiry_range": (90, 180),
            "stock_range": (40, 110),
            "demand_range": (20.0, 50.0),
            "elasticity_range": (-1.20, -0.80),
        },
        {
            "name": "Durum Wheat Spaghetti Pasta",
            "unit": "per 500 g pack",
            "cost_range": (68.0, 82.0),
            "markup_range": (0.28, 0.42),
            "expiry_range": (90, 180),
            "stock_range": (20, 60),
            "demand_range": (10.0, 25.0),
            "elasticity_range": (-1.60, -1.05),
        },
        {
            "name": "Whole Wheat Chakki Atta",
            "unit": "per 5 kg bag",
            "cost_range": (210.0, 235.0),
            "markup_range": (0.18, 0.26),
            "expiry_range": (60, 120),
            "stock_range": (25, 70),
            "demand_range": (15.0, 40.0),
            "elasticity_range": (-1.10, -0.70),
        },
        {
            "name": "Unpolished Toor Dal (Arhar)",
            "unit": "per kilogram",
            "cost_range": (138.0, 155.0),
            "markup_range": (0.20, 0.30),
            "expiry_range": (90, 180),
            "stock_range": (25, 70),
            "demand_range": (15.0, 35.0),
            "elasticity_range": (-1.20, -0.80),
        },
        {
            "name": "Kachi Ghani Mustard Oil",
            "unit": "per 1 litre bottle",
            "cost_range": (138.0, 155.0),
            "markup_range": (0.20, 0.30),
            "expiry_range": (90, 180),
            "stock_range": (20, 60),
            "demand_range": (12.0, 30.0),
            "elasticity_range": (-1.20, -0.75),
        },
        {
            "name": "Refined Sunflower Cooking Oil",
            "unit": "per 1 litre pouch",
            "cost_range": (118.0, 132.0),
            "markup_range": (0.18, 0.26),
            "expiry_range": (90, 180),
            "stock_range": (30, 80),
            "demand_range": (18.0, 45.0),
            "elasticity_range": (-1.20, -0.75),
        },
        {
            "name": "Instant Rolled Breakfast Oats",
            "unit": "per 500 g pack",
            "cost_range": (82.0, 96.0),
            "markup_range": (0.28, 0.40),
            "expiry_range": (90, 180),
            "stock_range": (15, 50),
            "demand_range": (8.0, 22.0),
            "elasticity_range": (-1.40, -0.90),
        },
        {
            "name": "Natural Creamy Peanut Butter",
            "unit": "per 500 g jar",
            "cost_range": (145.0, 170.0),
            "markup_range": (0.28, 0.42),
            "expiry_range": (90, 180),
            "stock_range": (12, 40),
            "demand_range": (6.0, 18.0),
            "elasticity_range": (-1.50, -1.00),
        },
        {
            "name": "Tata Iodized Salt",
            "unit": "per 1 kg pack",
            "cost_range": (19.0, 23.0),
            "markup_range": (0.20, 0.30),
            "expiry_range": (120, 180),
            "stock_range": (40, 100),
            "demand_range": (25.0, 60.0),
            "elasticity_range": (-0.80, -0.45),
        },
    ],
}

REQUIRED_COLUMNS: List[str] = [
    "product_id",
    "product_name",
    "category",
    "unit",
    "initial_stock",
    "unit_cost",
    "regular_price",
    "days_to_expiry",
    "daily_demand",
    "price_elasticity",
]


def generate_grocery_data(num_records: int = 120, seed: int = 42) -> pd.DataFrame:
    """Generate a reproducible synthetic Indian grocery inventory dataset.

    All monetary figures (unit_cost, regular_price) are generated in INR (₹).
    Prices and costs are product-specific rather than generated from generic bounds.

    Parameters
    ----------
    num_records : int, optional
        Number of product-batch records to generate (must be >= 120 for full coverage),
        by default 120.
    seed : int, optional
        Random seed for reproducibility, by default 42.

    Returns
    -------
    pd.DataFrame
        DataFrame containing synthetic grocery inventory records.
    """
    if num_records < 1:
        raise ValueError("num_records must be a positive integer.")

    rng = np.random.default_rng(seed)
    categories = list(PRODUCT_CATALOG.keys())

    records = []

    for idx in range(num_records):
        # Round-robin selection ensures balanced representation across categories
        category = categories[idx % len(categories)]
        category_items = PRODUCT_CATALOG[category]

        # Rotate through products within category so every product is represented
        item_idx = (idx // len(categories)) % len(category_items)
        item = category_items[item_idx]

        product_id = f"PROD-{idx + 1:04d}"
        product_name = item["name"]
        unit = item["unit"]

        # Product-specific unit cost in INR
        cost_min, cost_max = item["cost_range"]
        unit_cost = round(float(rng.uniform(cost_min, cost_max)), 2)

        # Product-specific regular price in INR, strictly ensuring regular_price > unit_cost
        markup_min, markup_max = item["markup_range"]
        markup_pct = float(rng.uniform(markup_min, markup_max))
        regular_price = round(unit_cost * (1.0 + markup_pct), 2)
        if regular_price <= unit_cost:
            regular_price = round(unit_cost + 2.00, 2)

        # Realistic days to expiry based on product perishability
        exp_min, exp_max = item["expiry_range"]
        days_to_expiry = int(rng.integers(exp_min, exp_max + 1))

        # Initial stock count
        stk_min, stk_max = item["stock_range"]
        initial_stock = int(rng.integers(stk_min, stk_max + 1))

        # Estimated daily baseline demand
        dem_min, dem_max = item["demand_range"]
        daily_demand = round(float(rng.uniform(dem_min, dem_max)), 1)

        # Negative price elasticity of demand
        elas_min, elas_max = item["elasticity_range"]
        price_elasticity = round(float(rng.uniform(elas_min, elas_max)), 2)

        records.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "unit": unit,
                "initial_stock": initial_stock,
                "unit_cost": unit_cost,
                "regular_price": regular_price,
                "days_to_expiry": days_to_expiry,
                "daily_demand": daily_demand,
                "price_elasticity": price_elasticity,
            }
        )

    df = pd.DataFrame(records, columns=REQUIRED_COLUMNS)
    return df


def save_dataset(df: pd.DataFrame, filepath: Path | str = DEFAULT_OUTPUT_FILE) -> Path:
    """Save the synthetic dataset to CSV.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset to save.
    filepath : Path | str, optional
        Target path for CSV file.

    Returns
    -------
    Path
        Path of the saved file.
    """
    dest_path = Path(filepath).resolve()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dest_path, index=False)
    return dest_path


def main() -> None:
    """CLI entrypoint for generating and saving the synthetic inventory."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic Indian grocery inventory dataset in INR for FreshPrice AI."
    )
    parser.add_argument(
        "--records",
        type=int,
        default=120,
        help="Number of records to generate (default: 120, minimum: 120 recommended).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible output (default: 42).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_FILE),
        help=f"Target CSV file path (default: {DEFAULT_OUTPUT_FILE}).",
    )

    args = parser.parse_args()

    print(
        f"Generating {args.records} synthetic Indian grocery records in INR (seed={args.seed})..."
    )
    df = generate_grocery_data(num_records=args.records, seed=args.seed)

    saved_path = save_dataset(df, args.output)
    print(f"Successfully generated and saved {len(df)} records to: {saved_path}")
    print("\nDataset Summary by Category (Monetary values in INR):")
    summary = df.groupby("category").agg(
        count=("product_id", "count"),
        avg_cost_inr=("unit_cost", "mean"),
        avg_price_inr=("regular_price", "mean"),
        avg_days_to_expiry=("days_to_expiry", "mean"),
        avg_elasticity=("price_elasticity", "mean"),
    )
    print(summary.round(2))


if __name__ == "__main__":
    main()
