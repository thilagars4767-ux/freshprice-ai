"""FreshPrice AI — One-Year Synthetic Grocery Operations & Demand Generator.

NEXAI 2026 Hackathon (PS 4.1: Track 4 Grocery Retail).

This module generates a comprehensive 365-day synthetic grocery retail dataset
for 20 perishable products across 4 categories (dairy, bakery, fruits, vegetables).
Total records: exactly 7,300 product-day rows (365 days * 20 products).

Datasets generated:
1. data/products.csv (Catalog metadata for 20 products)
2. data/historical_product_demand.csv (7,300 product-day operational and demand rows)
3. data/product_price_history.csv (7,300 price change records matching demand history)
4. data/inventory_batch_history.csv (Individual batch arrivals with FEFO tracking)
5. data/daily_store_history.csv (365 daily store-level aggregate reconciled rows)

SYNTHETIC DATA DISCLAIMER:
All dates, prices, discounts, stock levels, batch arrivals, customer demand draws,
and waste figures in these datasets are synthetic illustrative data generated
algorithmically for hackathon modeling, demonstration, and algorithmic evaluation.
They do NOT represent audited commercial supermarket POS records or real consumer transactions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from src.store_simulator import DEFAULT_DATA_DIR, DEFAULT_PRODUCTS, Product

DEFAULT_HISTORICAL_FILE = DEFAULT_DATA_DIR / "historical_product_demand.csv"


@dataclass
class BatchItem:
    """Internal tracker for a physical batch arriving at the store."""
    batch_id: str
    product_id: str
    manufacture_date: date
    expiry_date: date
    shelf_life_days: int
    quantity_received: float
    quantity_remaining: float
    unit_cost: float


def generate_products_dataset(products: Optional[List[Product]] = None) -> pd.DataFrame:
    """Generate the standardized 20-product definitions DataFrame.

    Columns:
    - product_id
    - product_name
    - category
    - regular_price
    - unit_cost
    - base_daily_demand
    - price_sensitivity
    - shelf_life_days
    """
    prods = products or list(DEFAULT_PRODUCTS)
    rows: List[Dict[str, Any]] = []

    for p in prods:
        rows.append(
            {
                "product_id": p.product_id,
                "product_name": p.name,
                "category": p.category,
                "regular_price": round(float(p.base_price), 2),
                "unit_cost": round(float(p.unit_cost), 2),
                "base_daily_demand": round(float(p.avg_daily_demand), 1),
                "price_sensitivity": round(float(p.price_sensitivity), 2),
                "shelf_life_days": int(p.shelf_life_days),
            }
        )

    return pd.DataFrame(rows)


def generate_full_synthetic_datasets(
    products: Optional[List[Product]] = None,
    days: int = 365,
    start_date: Optional[date] = None,
    seed: int = 101,
) -> Dict[str, pd.DataFrame]:
    """Generate comprehensive 365-day synthetic grocery retail datasets across 20 products.

    Parameters
    ----------
    products : Optional[List[Product]], optional
        Catalog of products, by default 20 canonical products.
    days : int, optional
        Number of consecutive days to simulate, default 365.
    start_date : Optional[date], optional
        Starting calendar date, default 2026-01-01.
    seed : int, optional
        Fixed random seed for reproducible stochastic generation, default 101.

    Returns
    -------
    Dict[str, pd.DataFrame]
        Dictionary containing:
        - "products": 20 rows
        - "historical_demand": days * len(products) rows (7,300 for 365 days)
        - "price_history": days * len(products) rows (7,300 for 365 days)
        - "inventory_batches": individual batch tracking records
        - "daily_store": days rows (365 rows)
    """
    if products is None:
        products = list(DEFAULT_PRODUCTS)

    if start_date is None:
        start_date = date(2026, 1, 1)

    rng = np.random.default_rng(seed)

    # Products DataFrame
    products_df = generate_products_dataset(products)

    # Low variation products (Royal Gala Apples strictly maintains 0% discount to test fallback)
    low_variation_pids = {"PROD-11"}

    # Tracking structures
    all_batches: List[BatchItem] = []
    active_batches_map: Dict[str, List[BatchItem]] = {p.product_id: [] for p in products}
    closing_stocks_map: Dict[str, float] = {p.product_id: 0.0 for p in products}

    demand_records: List[Dict[str, Any]] = []
    price_records: List[Dict[str, Any]] = []
    daily_store_records: List[Dict[str, Any]] = []

    batch_counter = 1

    for day_idx in range(days):
        current_date = start_date + timedelta(days=day_idx)
        weekday_name = current_date.strftime("%A")
        is_weekend = current_date.weekday() in (5, 6)

        # Day-level aggregation accumulators
        day_total_sold = 0.0
        day_total_wasted = 0.0
        day_total_revenue = 0.0
        day_total_cogs = 0.0
        day_total_ending_inv = 0.0

        for prod in products:
            p_id = prod.product_id
            regular_price = round(float(prod.base_price), 2)
            unit_cost = round(float(prod.unit_cost), 2)

            # 1. Opening Stock from previous day
            opening_stock = round(closing_stocks_map[p_id], 1)

            # 2. Batch Delivery / Receiving Logic
            # Scheduled deliveries occur every arrival_interval_days
            # In addition, emergency replenishment triggers if stock drops below 80% daily demand
            units_received = 0.0
            is_scheduled_arrival = (day_idx % prod.arrival_interval_days == 0)
            is_low_stock_urgent = (opening_stock < prod.avg_daily_demand * 0.8 and not is_scheduled_arrival)

            if is_scheduled_arrival or is_low_stock_urgent:
                order_qty = float(prod.batch_order_qty) if is_scheduled_arrival else round(prod.batch_order_qty * 0.75, 1)
                batch_id = f"BATCH-{batch_counter:05d}"
                batch_counter += 1

                mfg_date = current_date
                exp_date = current_date + timedelta(days=prod.shelf_life_days)

                new_batch = BatchItem(
                    batch_id=batch_id,
                    product_id=p_id,
                    manufacture_date=mfg_date,
                    expiry_date=exp_date,
                    shelf_life_days=int(prod.shelf_life_days),
                    quantity_received=order_qty,
                    quantity_remaining=order_qty,
                    unit_cost=unit_cost,
                )
                all_batches.append(new_batch)
                active_batches_map[p_id].append(new_batch)
                units_received = order_qty

            # 3. Morning Expiry Audit (FEFO check)
            # Batches on or after expiry date expire before store opens
            day_wasted = 0.0
            unexpired_batches: List[BatchItem] = []

            for b in active_batches_map[p_id]:
                if current_date >= b.expiry_date:
                    day_wasted += b.quantity_remaining
                    b.quantity_remaining = 0.0
                elif b.quantity_remaining > 1e-4:
                    unexpired_batches.append(b)

            day_wasted = round(day_wasted, 1)
            active_batches_map[p_id] = unexpired_batches

            # Calculate units available for sale
            units_available = round(sum(b.quantity_remaining for b in unexpired_batches), 1)

            # Expiry timeline for active stock
            if unexpired_batches:
                earliest_exp_batch = min(unexpired_batches, key=lambda b: (b.expiry_date, b.manufacture_date))
                earliest_exp_date = earliest_exp_batch.expiry_date
                earliest_mfg_date = min(b.manufacture_date for b in unexpired_batches)
                days_to_expiry = max(0, (earliest_exp_date - current_date).days)
                mfg_date_str = earliest_mfg_date.isoformat()
                exp_date_str = earliest_exp_date.isoformat()
            else:
                days_to_expiry = int(prod.shelf_life_days)
                mfg_date_str = current_date.isoformat()
                exp_date_str = (current_date + timedelta(days=prod.shelf_life_days)).isoformat()

            # 4. Price & Discount Decision
            if p_id in low_variation_pids:
                # Controlled zero variation to evaluate regression fallback
                discount_pct = 0.0
                actual_price = regular_price
                reason = "Regular price (catalog baseline)"
            elif units_available <= 1e-4:
                # Stockout condition
                discount_pct = 0.0
                actual_price = regular_price
                reason = "Regular price (stockout / zero inventory)"
            elif days_to_expiry <= 1:
                # Urgent clearance
                raw_disc = float(rng.choice([0.20, 0.30, 0.40], p=[0.15, 0.45, 0.40]))
                reason = f"Urgent clearance (<= 1 day to expiry)"
                tentative_p = round(regular_price * (1.0 - raw_disc), 2)
                if tentative_p < unit_cost:
                    actual_price = unit_cost
                    discount_pct = round((regular_price - actual_price) / regular_price * 100.0, 2)
                    reason += " (Capped at unit cost floor)"
                else:
                    actual_price = tentative_p
                    discount_pct = round(raw_disc * 100.0, 2)
            elif days_to_expiry <= 2:
                # Near-expiry markdown
                raw_disc = float(rng.choice([0.10, 0.15, 0.20], p=[0.25, 0.45, 0.30]))
                reason = f"Near-expiry markdown (<= 2 days to expiry)"
                tentative_p = round(regular_price * (1.0 - raw_disc), 2)
                if tentative_p < unit_cost:
                    actual_price = unit_cost
                    discount_pct = round((regular_price - actual_price) / regular_price * 100.0, 2)
                    reason += " (Capped at unit cost floor)"
                else:
                    actual_price = tentative_p
                    discount_pct = round(raw_disc * 100.0, 2)
            elif units_available > 2.2 * prod.avg_daily_demand * max(1, days_to_expiry):
                # Surplus stock clearance
                raw_disc = float(rng.choice([0.05, 0.10, 0.15], p=[0.30, 0.50, 0.20]))
                reason = "Surplus inventory clearance markdown"
                tentative_p = round(regular_price * (1.0 - raw_disc), 2)
                if tentative_p < unit_cost:
                    actual_price = unit_cost
                    discount_pct = round((regular_price - actual_price) / regular_price * 100.0, 2)
                    reason += " (Capped at unit cost floor)"
                else:
                    actual_price = tentative_p
                    discount_pct = round(raw_disc * 100.0, 2)
            elif is_weekend and rng.random() < 0.20:
                # Weekend promotional feature
                raw_disc = float(rng.choice([0.05, 0.10]))
                reason = "Weekend promotional feature"
                tentative_p = round(regular_price * (1.0 - raw_disc), 2)
                if tentative_p < unit_cost:
                    actual_price = unit_cost
                    discount_pct = round((regular_price - actual_price) / regular_price * 100.0, 2)
                    reason += " (Capped at unit cost floor)"
                else:
                    actual_price = tentative_p
                    discount_pct = round(raw_disc * 100.0, 2)
            else:
                discount_pct = 0.0
                actual_price = regular_price
                reason = "Regular price (sufficient shelf life)"

            # Ensure actual_price exactly equals regular_price * (1 - discount_pct/100) after rounding
            actual_price = round(actual_price, 2)

            # 5. Customer Demand Realization
            # Weekday multiplier: weekends +20%, Fridays +8%, Midweek -5%
            if current_date.weekday() in (5, 6):
                weekday_mult = 1.20
            elif current_date.weekday() == 4:
                weekday_mult = 1.08
            elif current_date.weekday() in (1, 2):
                weekday_mult = 0.95
            else:
                weekday_mult = 1.00

            # Lognormal consumer traffic shock
            shock = float(rng.lognormal(mean=0.0, sigma=0.10))
            base_demand = round(prod.avg_daily_demand * weekday_mult * shock, 1)

            # Price response: Q = base_demand * (1 + price_sensitivity * discount_fraction)
            disc_fraction = discount_pct / 100.0
            price_mult = 1.0 + (prod.price_sensitivity * disc_fraction)

            # Display promotion boost or reluctance
            if disc_fraction > 0.0:
                display_mult = 1.15
            elif days_to_expiry <= 2 and units_available > 0:
                display_mult = 0.85
            else:
                display_mult = 1.0

            realized_demand = max(0.0, round(base_demand * price_mult * display_mult, 1))

            # 6. FEFO Inventory Fulfillment (Earliest Expiry First)
            # Physical invariant: units_sold <= units_available
            units_sold = round(min(units_available, realized_demand), 1)

            rem_to_fulfill = units_sold
            # Sort unexpired batches: earliest expiry date first
            unexpired_batches.sort(key=lambda b: (b.expiry_date, b.manufacture_date))

            for b in unexpired_batches:
                if rem_to_fulfill <= 1e-4:
                    break
                fill = min(b.quantity_remaining, rem_to_fulfill)
                b.quantity_remaining = round(b.quantity_remaining - fill, 4)
                rem_to_fulfill = round(rem_to_fulfill - fill, 4)

            # Clean fully depleted batches
            active_batches_map[p_id] = [b for b in unexpired_batches if b.quantity_remaining > 1e-4]

            # Closing stock for today
            closing_stock = round(max(0.0, units_available - units_sold), 1)
            closing_stocks_map[p_id] = closing_stock

            # Verify physical inventory balance on this record:
            # closing_stock == opening_stock + units_received - units_wasted - units_sold
            expected_closing = round(opening_stock + units_received - day_wasted - units_sold, 1)
            if abs(closing_stock - expected_closing) > 0.15:
                # Guard against minor rounding drift
                closing_stock = max(0.0, expected_closing)
                closing_stocks_map[p_id] = closing_stock

            # Financial metrics
            rev = round(units_sold * actual_price, 2)
            cogs = round(units_sold * unit_cost, 2)
            gross_profit = round(rev - cogs, 2)

            # Accumulate store totals
            day_total_sold += units_sold
            day_total_wasted += day_wasted
            day_total_revenue += rev
            day_total_cogs += cogs
            day_total_ending_inv += closing_stock

            date_str = current_date.isoformat()

            # Record in Historical Demand
            demand_records.append(
                {
                    "date": date_str,
                    "product_id": p_id,
                    "product_name": prod.name,
                    "category": prod.category,
                    "regular_price": regular_price,
                    "actual_price": actual_price,
                    "discount_pct": discount_pct,
                    "unit_cost": unit_cost,
                    "opening_stock": opening_stock,
                    "units_received": units_received,
                    "units_available": units_available,
                    "units_sold": units_sold,
                    "units_wasted": day_wasted,
                    "closing_stock": closing_stock,
                    "manufacture_date": mfg_date_str,
                    "expiry_date": exp_date_str,
                    "days_to_expiry": days_to_expiry,
                    "weekday": weekday_name,
                    # Backwards compatibility aliases
                    "price": actual_price,
                    "base_demand": base_demand,
                    "price_sensitivity": round(float(prod.price_sensitivity), 2),
                }
            )

            # Record in Price History
            price_records.append(
                {
                    "date": date_str,
                    "product_id": p_id,
                    "product_name": prod.name,
                    "regular_price": regular_price,
                    "discount_pct": discount_pct,
                    "actual_price": actual_price,
                    "unit_cost": unit_cost,
                    "reason_for_price_change": reason,
                }
            )

        # Store-level daily aggregation
        day_total_gp = round(day_total_revenue - day_total_cogs, 2)
        daily_store_records.append(
            {
                "date": current_date.isoformat(),
                "units_sold": round(day_total_sold, 1),
                "units_wasted": round(day_total_wasted, 1),
                "revenue": round(day_total_revenue, 2),
                "cogs": round(day_total_cogs, 2),
                "gross_profit": day_total_gp,
                "ending_inventory": round(day_total_ending_inv, 1),
            }
        )

    # Build inventory batch history records
    batch_records: List[Dict[str, Any]] = []
    for b in all_batches:
        batch_records.append(
            {
                "batch_id": b.batch_id,
                "product_id": b.product_id,
                "manufacture_date": b.manufacture_date.isoformat(),
                "expiry_date": b.expiry_date.isoformat(),
                "shelf_life_days": b.shelf_life_days,
                "quantity_received": round(b.quantity_received, 1),
                "quantity_remaining": round(b.quantity_remaining, 1),
                "unit_cost": round(b.unit_cost, 2),
            }
        )

    historical_demand_df = pd.DataFrame(demand_records)
    price_history_df = pd.DataFrame(price_records)
    inventory_batch_df = pd.DataFrame(batch_records)
    daily_store_df = pd.DataFrame(daily_store_records)

    return {
        "products": products_df,
        "historical_demand": historical_demand_df,
        "price_history": price_history_df,
        "inventory_batches": inventory_batch_df,
        "daily_store": daily_store_df,
    }


def generate_historical_demand_dataset(
    products: Optional[List[Product]] = None,
    days: int = 365,
    start_date: Optional[date] = None,
    seed: int = 101,
) -> pd.DataFrame:
    """Convenience wrapper returning the historical demand DataFrame for compatibility."""
    bundle = generate_full_synthetic_datasets(
        products=products,
        days=days,
        start_date=start_date,
        seed=seed,
    )
    return bundle["historical_demand"]


def save_dataset_bundle(
    datasets: Dict[str, pd.DataFrame],
    output_dir: Union[Path, str] = DEFAULT_DATA_DIR,
) -> Dict[str, Path]:
    """Save all five generated dataset files to the target data directory."""
    dest_dir = Path(output_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    paths: Dict[str, Path] = {}

    # 1. products.csv
    prod_path = dest_dir / "products.csv"
    datasets["products"].to_csv(prod_path, index=False)
    paths["products_csv"] = prod_path

    # 2. historical_product_demand.csv
    demand_path = dest_dir / "historical_product_demand.csv"
    datasets["historical_demand"].to_csv(demand_path, index=False)
    paths["historical_demand_csv"] = demand_path

    # 3. product_price_history.csv
    price_path = dest_dir / "product_price_history.csv"
    datasets["price_history"].to_csv(price_path, index=False)
    paths["price_history_csv"] = price_path

    # 4. inventory_batch_history.csv
    batch_path = dest_dir / "inventory_batch_history.csv"
    datasets["inventory_batches"].to_csv(batch_path, index=False)
    paths["inventory_batches_csv"] = batch_path

    # 5. daily_store_history.csv
    store_path = dest_dir / "daily_store_history.csv"
    datasets["daily_store"].to_csv(store_path, index=False)
    paths["daily_store_csv"] = store_path

    return paths


def main() -> None:
    """CLI execution to generate all five synthetic grocery datasets."""
    parser = argparse.ArgumentParser(
        description="FreshPrice AI — One-Year Synthetic Grocery Operations & Demand Generator"
    )
    parser.add_argument("--days", type=int, default=365, help="Simulation duration in days (default 365).")
    parser.add_argument("--seed", type=int, default=101, help="Random seed for reproducibility (default 101).")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_DATA_DIR), help="Output directory for CSVs.")

    args = parser.parse_args()

    print(f"Generating {args.days} days of synthetic operations data for 20 products (Seed: {args.seed})...")
    datasets = generate_full_synthetic_datasets(days=args.days, seed=args.seed)

    saved_paths = save_dataset_bundle(datasets, output_dir=args.output_dir)
    print("\nSuccessfully generated and saved all 5 datasets:")
    for key, path in saved_paths.items():
        print(f"  - {key}: {path} ({len(datasets[key.replace('_csv', '').replace('historical_demand', 'historical_demand').replace('inventory_batches', 'inventory_batches').replace('price_history', 'price_history').replace('daily_store', 'daily_store').replace('products', 'products')])} rows)")


if __name__ == "__main__":
    main()
