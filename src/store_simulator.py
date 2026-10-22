"""NEXAI 2026 Hackathon (PS 4.1) — FreshPrice AI Store Simulator.

Problem Statement 4.1: Markdown Before Waste — Near-Expiry Pricing (Track 4: Grocery Retail).

This module implements a transparent, daily dynamic inventory simulation for a
single grocery store over 30 days modeling 20 perishable products. It benchmarks:
  A. Fixed-Price Policy (always charges base regular price)
  B. Markdown Policy (graduated discounts when products approach expiry)

Both policies execute on identical inventory arrivals, identical baseline demand shocks,
and identical initial conditions using a fixed random seed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Target output directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Product:
    """Perishable grocery catalog item."""
    product_id: str
    name: str
    category: str
    unit: str
    shelf_life_days: int
    unit_cost: float
    base_price: float
    avg_daily_demand: float
    price_sensitivity: float
    arrival_interval_days: int
    batch_order_qty: int


@dataclass
class InventoryBatch:
    """Physical product inventory batch with arrival and expiry tracking."""
    batch_id: str
    product_id: str
    arrival_day: int
    expiry_day: int
    initial_quantity: float
    remaining_quantity: float

    @property
    def is_empty(self) -> bool:
        return self.remaining_quantity <= 1e-5


@dataclass(frozen=True)
class MarkdownPolicyConfig:
    """Configurable near-expiry markdown discount thresholds."""
    threshold_1_days: int = 1     # 1 day to expiry
    discount_1_pct: float = 0.40  # 40% discount
    threshold_2_days: int = 2     # 2 days to expiry
    discount_2_pct: float = 0.20  # 20% discount
    enforce_cost_floor: bool = True


def get_shelf_life_aware_thresholds(
    shelf_life_days: int,
    config: MarkdownPolicyConfig,
) -> Tuple[int, int]:
    """Calculate effective markdown thresholds adjusted for product shelf life.

    Parameters
    ----------
    shelf_life_days : int
        Total shelf life in days of the product catalog item.
    config : MarkdownPolicyConfig
        Configured global markdown thresholds.

    Returns
    -------
    Tuple[int, int]
        (effective_threshold_1, effective_threshold_2)
        where:
        - effective_threshold_2 is bounded by max(1, shelf_life_days - 2)
        - effective_threshold_1 is bounded by effective_threshold_2
    """
    max_near_expiry_window = max(1, shelf_life_days - 2)
    effective_threshold_2 = min(config.threshold_2_days, max_near_expiry_window)
    # Urgent clearance threshold cannot exceed near-expiry threshold
    effective_threshold_1 = min(config.threshold_1_days, effective_threshold_2)
    return effective_threshold_1, effective_threshold_2


@dataclass
class DailyRecord:
    """Daily operational and financial record per product."""
    day: int
    policy: str
    product_id: str
    product_name: str
    category: str
    days_until_expiry: int
    regular_price: float
    selling_price: float
    discount_pct: float
    units_sold: float
    units_wasted: float
    revenue: float
    cogs: float
    gross_margin: float
    waste_cost: float
    ending_stock: float


@dataclass
class MarkdownEvent:
    """Historical audit record of an applied markdown."""
    day: int
    product_id: str
    product_name: str
    category: str
    days_until_expiry: int
    regular_price: float
    selling_price: float
    discount_pct: float
    units_sold: float
    units_wasted: float
    reason: str


@dataclass
class PolicyMetrics:
    """Reconciled 30-day cumulative retail metrics for a policy."""
    policy_name: str
    total_received: float
    units_sold: float
    units_wasted: float
    waste_rate_pct: float
    revenue: float
    cogs: float
    gross_margin: float
    gross_margin_pct: float
    total_waste_cost: float
    ending_inventory: float
    markdown_events_count: int


@dataclass
class SimulationResult:
    """Full comparative simulation package."""
    seed: int
    sim_days: int
    fixed_metrics: PolicyMetrics
    markdown_metrics: PolicyMetrics
    daily_history_df: pd.DataFrame
    markdown_events_df: pd.DataFrame
    comparison_summary_df: pd.DataFrame
    products_df: pd.DataFrame


# ---------------------------------------------------------------------------
# Catalog Definition: 20 Perishable Grocery Products (INR)
# ---------------------------------------------------------------------------

DEFAULT_PRODUCTS: List[Product] = [
    # Dairy (5 products)
    Product("PROD-01", "Toned Fresh Milk", "dairy", "per litre", 3, 52.00, 60.00, 35.0, 1.4, 2, 75),
    Product("PROD-02", "Full Cream Fresh Milk", "dairy", "per litre", 3, 64.00, 74.00, 30.0, 1.3, 2, 65),
    Product("PROD-03", "Fresh Curd / Dahi", "dairy", "per 500 g pack", 6, 32.00, 42.00, 25.0, 1.5, 3, 50),
    Product("PROD-04", "Malai Paneer", "dairy", "per 200 g pack", 5, 82.00, 105.00, 18.0, 1.6, 3, 40),
    Product("PROD-05", "Spiced Buttermilk / Chaas", "dairy", "per 500 ml pouch", 4, 13.00, 18.00, 28.0, 1.5, 2, 60),
    # Bakery (5 products)
    Product("PROD-06", "White Sandwich Bread", "bakery", "per loaf", 4, 30.00, 40.00, 30.0, 1.7, 2, 65),
    Product("PROD-07", "Whole Wheat Atta Bread", "bakery", "per loaf", 4, 38.00, 50.00, 22.0, 1.6, 2, 50),
    Product("PROD-08", "Ladi Pav", "bakery", "per 6-piece pack", 3, 20.00, 28.00, 35.0, 1.8, 2, 75),
    Product("PROD-09", "Brioche Burger Buns", "bakery", "per 4-piece pack", 4, 30.00, 42.00, 18.0, 1.7, 2, 40),
    Product("PROD-10", "Garlic Herb Baguette", "bakery", "per loaf", 3, 50.00, 68.00, 12.0, 1.9, 2, 28),
    # Fruits (5 products)
    Product("PROD-11", "Royal Gala Apples", "fruits", "per kilogram", 8, 130.00, 180.00, 22.0, 1.5, 4, 60),
    Product("PROD-12", "Robusta Cavendish Bananas", "fruits", "per dozen", 4, 40.00, 58.00, 35.0, 1.8, 2, 75),
    Product("PROD-13", "Nagpur Mandarin Oranges", "fruits", "per kilogram", 7, 62.00, 88.00, 20.0, 1.6, 3, 50),
    Product("PROD-14", "Green Seedless Grapes", "fruits", "per 500 g pack", 5, 50.00, 72.00, 18.0, 1.8, 3, 45),
    Product("PROD-15", "Semi-Ripe Papaya", "fruits", "per kilogram", 4, 28.00, 42.00, 20.0, 1.7, 2, 45),
    # Vegetables (5 products)
    Product("PROD-16", "Hybrid Tomatoes (Tamatar)", "vegetables", "per kilogram", 5, 24.00, 36.00, 40.0, 1.6, 2, 85),
    Product("PROD-17", "Fresh White Cauliflower", "vegetables", "per head", 5, 24.00, 36.00, 25.0, 1.7, 3, 55),
    Product("PROD-18", "Baby Spinach (Palak)", "vegetables", "per 250 g bunch", 3, 14.00, 22.00, 32.0, 1.9, 2, 70),
    Product("PROD-19", "Green Capsicum (Shimla Mirch)", "vegetables", "per 500 g pack", 5, 30.00, 45.00, 18.0, 1.6, 3, 45),
    Product("PROD-20", "Fresh Button Mushrooms", "vegetables", "per 200 g pack", 4, 40.00, 58.00, 16.0, 1.8, 2, 38),
]


def get_default_products() -> List[Product]:
    """Return a copy of the standard 20 perishable grocery products."""
    return list(DEFAULT_PRODUCTS)


# ---------------------------------------------------------------------------
# Pre-Simulation Schedules: Controlled Seed for 100% Identical Conditions
# ---------------------------------------------------------------------------

def generate_arrival_schedule(
    products: List[Product], sim_days: int = 30, seed: int = 42
) -> List[InventoryBatch]:
    """Generate scheduled batch arrivals for all products across the simulation window.

    Deterministic scheduling based on product arrival interval guarantees both
    policies receive the exact same inventory quantities on the exact same days.
    """
    batches: List[InventoryBatch] = []
    batch_counter = 1

    for prod in products:
        day = 1
        while day <= sim_days:
            # Batch arriving on `day` with `shelf_life_days`
            expiry_day = day + prod.shelf_life_days
            batch_id = f"BATCH-{batch_counter:04d}"
            batch_counter += 1
            batches.append(
                InventoryBatch(
                    batch_id=batch_id,
                    product_id=prod.product_id,
                    arrival_day=day,
                    expiry_day=expiry_day,
                    initial_quantity=float(prod.batch_order_qty),
                    remaining_quantity=float(prod.batch_order_qty),
                )
            )
            day += prod.arrival_interval_days

    return batches


def generate_baseline_demand_draws(
    products: List[Product], sim_days: int = 30, seed: int = 42
) -> Dict[Tuple[str, int], float]:
    """Pre-generate daily baseline consumer demand draws using a controlled random seed.

    Returns mapping of (product_id, day) -> baseline demand units.
    Pre-generating baseline demand ensures both Fixed and Markdown policies face
    the exact same underlying customer shopping traffic on every simulated day.
    """
    rng = np.random.default_rng(seed)
    demand_draws: Dict[Tuple[str, int], float] = {}

    for day in range(1, sim_days + 1):
        for prod in products:
            # Poisson demand draw around product's baseline velocity
            raw_draw = rng.poisson(lam=prod.avg_daily_demand)
            # Add slight random shopper traffic variation
            demand_draws[(prod.product_id, day)] = max(1.0, float(raw_draw))

    return demand_draws


# ---------------------------------------------------------------------------
# Daily Store Simulator Engine
# ---------------------------------------------------------------------------

def simulate_single_policy(
    policy_name: str,
    products: List[Product],
    arrival_batches: List[InventoryBatch],
    baseline_demand: Dict[Tuple[str, int], float],
    sim_days: int = 30,
    config: MarkdownPolicyConfig = MarkdownPolicyConfig(),
) -> Tuple[PolicyMetrics, List[DailyRecord], List[MarkdownEvent]]:
    """Execute 30-day store simulation for a specific pricing policy.

    Parameters
    ----------
    policy_name : str
        "fixed" or "markdown".
    products : List[Product]
        List of 20 perishable products.
    arrival_batches : List[InventoryBatch]
        Pre-scheduled batch arrivals.
    baseline_demand : Dict[Tuple[str, int], float]
        Pre-drawn daily baseline demand mapping.
    sim_days : int, optional
        Simulation duration in days, default 30.
    config : MarkdownPolicyConfig, optional
        Markdown discount and threshold parameters.

    Returns
    -------
    Tuple[PolicyMetrics, List[DailyRecord], List[MarkdownEvent]]
        Aggregate metrics, daily product records, and markdown events.
    """
    prod_map: Dict[str, Product] = {p.product_id: p for p in products}

    # Deep copy inventory batches so policies operate on independent inventory
    batches_pool: List[InventoryBatch] = [
        InventoryBatch(
            batch_id=b.batch_id,
            product_id=b.product_id,
            arrival_day=b.arrival_day,
            expiry_day=b.expiry_day,
            initial_quantity=b.initial_quantity,
            remaining_quantity=b.initial_quantity,
        )
        for b in arrival_batches
    ]

    active_inventory: List[InventoryBatch] = []
    daily_records: List[DailyRecord] = []
    markdown_events: List[MarkdownEvent] = []

    total_units_received = sum(b.initial_quantity for b in arrival_batches)
    total_units_sold = 0.0
    total_units_wasted = 0.0
    total_revenue = 0.0
    total_cogs = 0.0
    total_waste_cost = 0.0

    for current_day in range(1, sim_days + 1):
        # 1. Receive scheduled inventory arrivals for current_day
        new_arrivals = [b for b in batches_pool if b.arrival_day == current_day]
        active_inventory.extend(new_arrivals)

        for prod in products:
            p_id = prod.product_id
            prod_batches = [b for b in active_inventory if b.product_id == p_id and not b.is_empty]

            # 2. Expiry check: Products on or after expiry day (current_day >= expiry_day) expire
            day_wasted = 0.0
            unexpired_batches: List[InventoryBatch] = []

            for b in prod_batches:
                if current_day >= b.expiry_day:
                    # Expired before store opens on current_day
                    day_wasted += b.remaining_quantity
                    b.remaining_quantity = 0.0
                else:
                    unexpired_batches.append(b)

            total_units_wasted += day_wasted
            prod_waste_cost = round(day_wasted * prod.unit_cost, 2)
            total_waste_cost += prod_waste_cost

            # Update active inventory
            active_inventory = [b for b in active_inventory if not b.is_empty]

            # Current minimum days until expiry among available unexpired batches
            if unexpired_batches:
                min_days_to_expiry = min(b.expiry_day - current_day for b in unexpired_batches)
                current_stock = sum(b.remaining_quantity for b in unexpired_batches)
            else:
                min_days_to_expiry = 0
                current_stock = 0.0

            # 3. Determine selling price according to selected policy
            selling_price = prod.base_price
            discount_pct = 0.0
            discount_reason = "Regular price"

            if policy_name == "markdown" and unexpired_batches:
                eff_t1, eff_t2 = get_shelf_life_aware_thresholds(prod.shelf_life_days, config)

                # Precedence Rule:
                # 1. Urgent clearance takes highest precedence if min_days_to_expiry <= eff_t1 and discount_1_pct > 0.
                # 2. Near-expiry markdown applies only if urgent clearance does not apply, min_days_to_expiry <= eff_t2, and discount_2_pct > 0.
                # 3. Exactly one discount applies; discounts never stack or combine.
                if min_days_to_expiry <= eff_t1 and config.discount_1_pct > 0.0:
                    raw_discount = config.discount_1_pct
                    discount_reason = f"Urgent clearance (<= {eff_t1} {'day' if eff_t1 == 1 else 'days'} to expiry)"
                elif min_days_to_expiry <= eff_t2 and config.discount_2_pct > 0.0:
                    raw_discount = config.discount_2_pct
                    discount_reason = f"Near-expiry markdown (<= {eff_t2} {'day' if eff_t2 == 1 else 'days'} to expiry)"
                else:
                    raw_discount = 0.0
                    discount_reason = "Sufficient shelf life remaining"

                if raw_discount > 0.0:
                    tentative_price = round(prod.base_price * (1.0 - raw_discount), 2)
                    if config.enforce_cost_floor and tentative_price < prod.unit_cost:
                        # Price floor: selling price cannot fall below unit cost
                        selling_price = prod.unit_cost
                        discount_pct = round((prod.base_price - selling_price) / prod.base_price, 4)
                        discount_reason += " (Capped at unit cost floor)"
                    else:
                        selling_price = tentative_price
                        discount_pct = raw_discount

            # 4. Calculate daily demand (depends on price discount and expiry urgency)
            base_d = baseline_demand.get((p_id, current_day), prod.avg_daily_demand)

            # Price response: Q_adj = Q_base * (1 + sensitivity * discount)
            price_multiplier = 1.0 + (prod.price_sensitivity * discount_pct)

            # Expiry display effect:
            # Under fixed pricing, consumers avoid stock with only 1-2 days left without discount.
            # Under markdown, promotional clearance attracts bargain-seeking immediate-use shoppers.
            if discount_pct > 0.0:
                expiry_multiplier = 1.15  # Promotional discount display effect
            elif min_days_to_expiry in (1, 2) and current_stock > 0:
                expiry_multiplier = 0.85  # Consumer reluctance to buy near-expiry at full price
            else:
                expiry_multiplier = 1.0

            realized_demand = max(0.0, round(base_d * price_multiplier * expiry_multiplier, 1))

            # 5. Fulfill demand from available unexpired inventory using FEFO
            # Sort batches: earliest expiry_day first
            unexpired_batches.sort(key=lambda b: (b.expiry_day, b.arrival_day))

            day_sold = 0.0
            remaining_demand = realized_demand

            for b in unexpired_batches:
                if remaining_demand <= 1e-5:
                    break
                fill = min(b.remaining_quantity, remaining_demand)
                b.remaining_quantity -= fill
                day_sold += fill
                remaining_demand -= fill

            day_revenue = round(day_sold * selling_price, 2)
            day_cogs = round(day_sold * prod.unit_cost, 2)
            day_margin = round(day_revenue - day_cogs, 2)

            total_units_sold += day_sold
            total_revenue += day_revenue
            total_cogs += day_cogs

            ending_prod_stock = sum(b.remaining_quantity for b in unexpired_batches)

            # 6. Record daily product history
            rec = DailyRecord(
                day=current_day,
                policy=policy_name,
                product_id=p_id,
                product_name=prod.name,
                category=prod.category,
                days_until_expiry=min_days_to_expiry,
                regular_price=prod.base_price,
                selling_price=selling_price,
                discount_pct=round(discount_pct * 100.0, 2),
                units_sold=round(day_sold, 1),
                units_wasted=round(day_wasted, 1),
                revenue=day_revenue,
                cogs=day_cogs,
                gross_margin=day_margin,
                waste_cost=prod_waste_cost,
                ending_stock=round(ending_prod_stock, 1),
            )
            daily_records.append(rec)

            # 7. Record markdown event if discount was applied
            if discount_pct > 0.0 and day_sold > 0.0:
                m_event = MarkdownEvent(
                    day=current_day,
                    product_id=p_id,
                    product_name=prod.name,
                    category=prod.category,
                    days_until_expiry=min_days_to_expiry,
                    regular_price=prod.base_price,
                    selling_price=selling_price,
                    discount_pct=round(discount_pct * 100.0, 2),
                    units_sold=round(day_sold, 1),
                    units_wasted=round(day_wasted, 1),
                    reason=discount_reason,
                )
                markdown_events.append(m_event)

    # Clean active inventory after Day 30
    ending_inventory = sum(b.remaining_quantity for b in active_inventory if not b.is_empty)

    # Standard GAAP Metrics Definition:
    # Waste Rate = Wasted Units / Total Received Units
    # Gross Margin = Revenue - COGS
    # Gross Margin % = Gross Margin / Revenue
    waste_rate_pct = round((total_units_wasted / total_units_received) * 100.0, 2) if total_units_received > 0 else 0.0
    total_gross_margin = round(total_revenue - total_cogs, 2)
    gross_margin_pct = round((total_gross_margin / total_revenue) * 100.0, 2) if total_revenue > 0 else 0.0

    metrics = PolicyMetrics(
        policy_name="Fixed-Price Baseline" if policy_name == "fixed" else "Dynamic Markdown Policy",
        total_received=round(total_units_received, 1),
        units_sold=round(total_units_sold, 1),
        units_wasted=round(total_units_wasted, 1),
        waste_rate_pct=waste_rate_pct,
        revenue=round(total_revenue, 2),
        cogs=round(total_cogs, 2),
        gross_margin=total_gross_margin,
        gross_margin_pct=gross_margin_pct,
        total_waste_cost=round(total_waste_cost, 2),
        ending_inventory=round(ending_inventory, 1),
        markdown_events_count=len(markdown_events),
    )

    return metrics, daily_records, markdown_events


def run_store_simulation(
    sim_days: int = 30,
    seed: int = 42,
    config: MarkdownPolicyConfig = MarkdownPolicyConfig(),
    products: Optional[List[Product]] = None,
) -> SimulationResult:
    """Execute synchronized 30-day grocery simulation comparing Fixed vs Markdown pricing.

    Both policies use identical product definitions, identical arrival schedules,
    and identical baseline customer demand draws generated using `seed`.

    Parameters
    ----------
    sim_days : int, optional
        Duration of store simulation in days, default 30.
    seed : int, optional
        Random seed for reproducibility, default 42.
    config : MarkdownPolicyConfig, optional
        Markdown thresholds and discount percentages.
    products : Optional[List[Product]], optional
        Catalog of products, by default 20 standard perishable products.

    Returns
    -------
    SimulationResult
        Comprehensive result package with metrics, daily histories, and events.
    """
    if products is None:
        products = get_default_products()

    # Step A: Pre-generate arrival schedule and baseline demand draws
    arrivals = generate_arrival_schedule(products, sim_days=sim_days, seed=seed)
    demand_draws = generate_baseline_demand_draws(products, sim_days=sim_days, seed=seed)

    # Step B: Run Policy A (Fixed-Price Baseline)
    fixed_metrics, fixed_daily, _ = simulate_single_policy(
        policy_name="fixed",
        products=products,
        arrival_batches=arrivals,
        baseline_demand=demand_draws,
        sim_days=sim_days,
        config=config,
    )

    # Step C: Run Policy B (Markdown Policy)
    markdown_metrics, markdown_daily, markdown_events = simulate_single_policy(
        policy_name="markdown",
        products=products,
        arrival_batches=arrivals,
        baseline_demand=demand_draws,
        sim_days=sim_days,
        config=config,
    )

    # Convert to DataFrames
    all_daily_records = fixed_daily + markdown_daily
    daily_history_df = pd.DataFrame([asdict(r) for r in all_daily_records])
    markdown_events_df = pd.DataFrame([asdict(e) for e in markdown_events]) if markdown_events else pd.DataFrame(
        columns=[
            "day", "product_id", "product_name", "category", "days_until_expiry",
            "regular_price", "selling_price", "discount_pct", "units_sold", "units_wasted", "reason"
        ]
    )

    # Comparative Summary DataFrame
    f = fixed_metrics
    m = markdown_metrics

    waste_units_saved = round(f.units_wasted - m.units_wasted, 1)
    waste_reduction_pct = round(((f.units_wasted - m.units_wasted) / f.units_wasted) * 100.0, 2) if f.units_wasted > 0 else 0.0
    revenue_diff = round(m.revenue - f.revenue, 2)
    margin_diff = round(m.gross_margin - f.gross_margin, 2)

    summary_rows = [
        {"Metric": "Initial Inventory Received (units)", "Fixed-Price Policy": f.total_received, "Markdown Policy": m.total_received, "Difference": 0.0},
        {"Metric": "Units Sold", "Fixed-Price Policy": f.units_sold, "Markdown Policy": m.units_sold, "Difference": round(m.units_sold - f.units_sold, 1)},
        {"Metric": "Units Wasted (Expired)", "Fixed-Price Policy": f.units_wasted, "Markdown Policy": m.units_wasted, "Difference": -waste_units_saved},
        {"Metric": "Waste Rate (%)", "Fixed-Price Policy": f"{f.waste_rate_pct:.2f}%", "Markdown Policy": f"{m.waste_rate_pct:.2f}%", "Difference": f"-{f.waste_rate_pct - m.waste_rate_pct:.2f}%"},
        {"Metric": "Waste Reduction (%)", "Fixed-Price Policy": "0.00%", "Markdown Policy": f"{waste_reduction_pct:.2f}%", "Difference": f"{waste_reduction_pct:.2f}%"},
        {"Metric": "Total Revenue (INR)", "Fixed-Price Policy": f.revenue, "Markdown Policy": m.revenue, "Difference": revenue_diff},
        {"Metric": "Cost of Goods Sold - COGS (INR)", "Fixed-Price Policy": f.cogs, "Markdown Policy": m.cogs, "Difference": round(m.cogs - f.cogs, 2)},
        {"Metric": "Gross Margin (INR)", "Fixed-Price Policy": f.gross_margin, "Markdown Policy": m.gross_margin, "Difference": margin_diff},
        {"Metric": "Gross Margin (%)", "Fixed-Price Policy": f"{f.gross_margin_pct:.2f}%", "Markdown Policy": f"{m.gross_margin_pct:.2f}%", "Difference": f"{m.gross_margin_pct - f.gross_margin_pct:+.2f}%"},
        {"Metric": "Markdown Events Recorded", "Fixed-Price Policy": 0, "Markdown Policy": m.markdown_events_count, "Difference": m.markdown_events_count},
    ]
    comparison_summary_df = pd.DataFrame(summary_rows)

    products_df = pd.DataFrame([asdict(p) for p in products])

    return SimulationResult(
        seed=seed,
        sim_days=sim_days,
        fixed_metrics=fixed_metrics,
        markdown_metrics=markdown_metrics,
        daily_history_df=daily_history_df,
        markdown_events_df=markdown_events_df,
        comparison_summary_df=comparison_summary_df,
        products_df=products_df,
    )


def export_mvp_csv_outputs(
    sim_result: SimulationResult, output_dir: Path | str = DEFAULT_DATA_DIR
) -> Dict[str, Path]:
    """Export the official NEXAI MVP simulation outputs to CSV."""
    dest_dir = Path(output_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    paths: Dict[str, Path] = {}

    # 1. Product definition catalog
    prod_path = dest_dir / "mvp_products.csv"
    sim_result.products_df.to_csv(prod_path, index=False)
    paths["products_csv"] = prod_path

    # 2. Daily simulation history
    daily_path = dest_dir / "daily_simulation_history.csv"
    sim_result.daily_history_df.to_csv(daily_path, index=False)
    paths["daily_history_csv"] = daily_path

    # 3. Policy comparison summary
    comp_path = dest_dir / "policy_comparison_summary.csv"
    sim_result.comparison_summary_df.to_csv(comp_path, index=False)
    paths["comparison_summary_csv"] = comp_path

    # 4. Markdown events history
    events_path = dest_dir / "markdown_events_history.csv"
    sim_result.markdown_events_df.to_csv(events_path, index=False)
    paths["markdown_events_csv"] = events_path

    return paths


# ---------------------------------------------------------------------------
# CLI Execution
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI execution for the store simulator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="FreshPrice AI — 30-Day Store Simulator (NEXAI 2026 Hackathon PS 4.1)"
    )
    parser.add_argument("--days", type=int, default=30, help="Simulation duration (default 30).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42).")
    parser.add_argument("--t1", type=int, default=1, help="Threshold 1 days to expiry (default 1).")
    parser.add_argument("--d1", type=float, default=0.40, help="Discount 1 percentage (default 0.40).")
    parser.add_argument("--t2", type=int, default=2, help="Threshold 2 days to expiry (default 2).")
    parser.add_argument("--d2", type=float, default=0.20, help="Discount 2 percentage (default 0.20).")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_DATA_DIR), help="Output directory for CSVs.")

    args = parser.parse_args()

    cfg = MarkdownPolicyConfig(
        threshold_1_days=args.t1,
        discount_1_pct=args.d1,
        threshold_2_days=args.t2,
        discount_2_pct=args.d2,
    )

    print(f"Running FreshPrice AI 30-Day Store Simulator (Seed: {args.seed}, Days: {args.days})...")
    res = run_store_simulation(sim_days=args.days, seed=args.seed, config=cfg)

    print("\n" + "=" * 65)
    print("NEXAI 2026: POLICY COMPARISON SUMMARY (30 DAYS, 20 PRODUCTS)")
    print("=" * 65)
    print(res.comparison_summary_df.to_string(index=False))
    print("=" * 65)

    saved = export_mvp_csv_outputs(res, output_dir=args.output_dir)
    print("\nSaved MVP CSV Deliverables:")
    for k, v in saved.items():
        print(f"  - {k}: {v}")


if __name__ == "__main__":
    main()
