"""Dynamic Pricing Engine & Inventory Shelf-Life Simulator for FreshPrice AI.

NOTE ON CURRENCY & DATA ORIGIN:
All monetary figures (unit_cost, regular_price, selling_price, revenue, COGS,
gross_profit, waste_loss, total_inventory_cost, net_profit) are denominated in
INR (Indian Rupees - ₹).
All calculations are deterministic and based on synthetic grocery simulation data.
They do NOT represent actual supermarket sales or financial guarantees.

ACCOUNTING IDENTITIES & DEFINITIONS:
1. Revenue = Units Sold * Selling Price
2. COGS (Cost of Goods Sold) = Units Sold * Unit Cost
3. Gross Profit on Sold Units = Revenue - COGS = Units Sold * (Selling Price - Unit Cost)
4. Waste Loss (Spoilage Cost) = Unsold Units * Unit Cost
5. Total Initial Inventory Cost = Initial Stock * Unit Cost = COGS + Waste Loss
6. Net Retail Profit (Profit after Inventory Waste) = Revenue - Total Initial Inventory Cost
   Identical to: Gross Profit - Waste Loss
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_INVENTORY_FILE = DEFAULT_DATA_DIR / "synthetic_grocery_inventory.csv"


@dataclass(frozen=True)
class PricingPolicyConfig:
    """Configuration parameters for the dynamic markdown pricing policy.

    Attributes
    ----------
    max_discount : float
        Upper bound on allowed markdown discount (e.g. 0.40 for 40% maximum discount).
    min_margin_buffer : float
        Minimum profit margin buffer above unit cost (0.0 means selling at cost is the hard floor).
    expiry_urgency_days : int
        Threshold days to expiry considered urgent for clearance.
    max_demand_multiplier : float
        Maximum demand expansion multiplier allowed under elasticity to avoid unrealistic spikes.
    """

    max_discount: float = 0.40
    min_margin_buffer: float = 0.0
    expiry_urgency_days: int = 3
    max_demand_multiplier: float = 3.0


@dataclass
class BatchSimulationResult:
    """Detailed simulation and financial accounting record for a single product batch.

    Units Sold and Unsold Units are deterministic expected continuous quantities
    (expected values) over the remaining shelf-life window.
    """

    product_id: str
    product_name: str
    category: str
    unit: str
    strategy: str
    initial_stock: int
    unit_cost: float
    regular_price: float
    selling_price: float
    discount_pct: float
    days_to_expiry: int
    daily_demand: float
    effective_daily_demand: float
    units_sold: float
    unsold_units: float
    revenue: float
    cogs: float
    gross_profit: float
    waste_loss: float
    total_inventory_cost: float
    net_profit: float
    waste_rate_pct: float
    has_waste: bool
    limitation_reason: str = ""

    # Aliases for backward compatibility
    @property
    def total_cost(self) -> float:
        return self.total_inventory_cost

    @property
    def waste_cost(self) -> float:
        return self.waste_loss

    @property
    def profit(self) -> float:
        return self.net_profit


@dataclass
class StrategyMetrics:
    """Aggregate performance and financial reconciliation metrics for a strategy."""

    strategy_name: str
    total_batches: int
    total_initial_stock: int
    total_units_sold: float
    total_unsold_units: float
    waste_rate_pct: float
    total_revenue: float
    total_cogs: float
    total_gross_profit: float
    total_waste_loss: float
    total_inventory_cost: float
    total_net_profit: float
    average_discount_pct: float
    batches_with_waste: int


def load_inventory(filepath: Path | str = DEFAULT_INVENTORY_FILE) -> pd.DataFrame:
    """Load grocery inventory dataset from CSV file.

    Parameters
    ----------
    filepath : Path | str
        Path to the inventory CSV file.

    Returns
    -------
    pd.DataFrame
        Loaded inventory DataFrame.
    """
    path = Path(filepath).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Inventory dataset not found at: {path}")
    df = pd.read_csv(path)
    return df


def calculate_demand_response(
    baseline_demand: float,
    discount_pct: float,
    price_elasticity: float,
    max_multiplier: float = 3.0,
) -> float:
    r"""Calculate stimulated daily demand using standard Price Elasticity of Demand.

    Equation
    --------
    .. math::
        Q_{adj} = Q_0 \times \left(1 + E_d \times \frac{\Delta P}{P_0}\right)
                = Q_0 \times (1 - E_d \times d)
                = Q_0 \times (1 + |E_d| \times d)

    Where:
    - :math:`Q_0` is the baseline daily demand at regular price.
    - :math:`E_d` is the price elasticity of demand (negative for normal grocery items).
    - :math:`d` is the discount fraction (:math:`0 \le d \le d_{\max}`).
    - Since :math:`E_d < 0`, :math:`-E_d > 0`, discounts increase demand.

    Assumptions
    -----------
    - Demand response is linear over moderate discount ranges (0% to 40%).
    - A configurable `max_multiplier` caps demand expansion to prevent unrealistic spikes.
    - Demand is strictly non-negative.
    """
    if baseline_demand <= 0.0:
        return 0.0

    abs_elasticity = abs(price_elasticity)
    multiplier = 1.0 + (abs_elasticity * max(0.0, discount_pct))
    multiplier = min(multiplier, max_multiplier)
    effective_demand = round(baseline_demand * multiplier, 2)
    return max(0.0, effective_demand)


def recommend_dynamic_price(
    initial_stock: int,
    unit_cost: float,
    regular_price: float,
    days_to_expiry: int,
    daily_demand: float,
    price_elasticity: float,
    config: PricingPolicyConfig = PricingPolicyConfig(),
) -> Tuple[float, float, str]:
    """Recommend dynamic markdown price and discount for a product batch.

    Evaluates whether a markdown is genuinely profitable vs baseline using identical
    inventory, shelf-life, demand, and accounting rules. Never recommends selling
    below unit_cost.

    Parameters
    ----------
    initial_stock : int
        Current batch stock count.
    unit_cost : float
        Wholesale unit cost in INR.
    regular_price : float
        Standard regular selling price in INR.
    days_to_expiry : int
        Days until batch expiration.
    daily_demand : float
        Baseline daily demand in units/day.
    price_elasticity : float
        Price elasticity coefficient (negative).
    config : PricingPolicyConfig
        Pricing policy constraints.

    Returns
    -------
    Tuple[float, float, str]
        (recommended_price, discount_percentage, limitation_or_action_reason)
    """
    # 1. Price floor constraint: selling price must NEVER fall below unit_cost
    min_allowable_price = round(unit_cost * (1.0 + config.min_margin_buffer), 2)

    if regular_price <= min_allowable_price:
        return (
            regular_price,
            0.0,
            "Price floor constraint: unit cost equals or exceeds regular price; markdown not profitable",
        )

    # Maximum mathematically allowable discount before breaching cost floor
    max_margin_discount = (regular_price - min_allowable_price) / regular_price
    effective_max_discount = min(config.max_discount, max_margin_discount)

    if effective_max_discount <= 0.001:
        return (
            regular_price,
            0.0,
            "Price floor constraint: insufficient margin above unit cost for profitable markdown",
        )

    # If inventory or shelf life is zero
    if initial_stock <= 0 or days_to_expiry <= 0 or daily_demand <= 0.0:
        return (
            regular_price,
            0.0,
            "No active stock or shelf-life remaining; markdown not applicable",
        )

    # Expected baseline demand over remaining shelf life at regular price
    expected_baseline_demand = daily_demand * days_to_expiry
    coverage_ratio = initial_stock / max(expected_baseline_demand, 0.001)

    # Total batch inventory cost (constant across strategies)
    total_inventory_cost = round(float(initial_stock) * unit_cost, 2)

    # Baseline performance at regular price
    base_sold = min(float(initial_stock), expected_baseline_demand)
    base_rev = round(base_sold * regular_price, 2)
    base_net_profit = round(base_rev - total_inventory_cost, 2)
    base_waste = initial_stock - base_sold

    # If baseline demand easily clears inventory and expiry is not imminent, retain regular price
    if coverage_ratio <= 1.0 and days_to_expiry > config.expiry_urgency_days:
        return (
            regular_price,
            0.0,
            "Sufficient baseline demand: full stock expected to sell at regular price",
        )

    abs_elasticity = max(0.1, abs(price_elasticity))

    # Calculate clearance discount needed to absorb excess inventory:
    # 1 - Ed * d = coverage_ratio  =>  d = (coverage_ratio - 1) / |Ed|
    if coverage_ratio > 1.0:
        d_clearance = (coverage_ratio - 1.0) / abs_elasticity
    else:
        d_clearance = 0.0

    # Expiry urgency component: discounts scale up as expiry draws closer
    if days_to_expiry <= 1:
        d_expiry = 0.20
    elif days_to_expiry <= 2:
        d_expiry = 0.10
    elif days_to_expiry <= config.expiry_urgency_days:
        d_expiry = 0.05
    else:
        d_expiry = 0.0

    # Candidate discounts to evaluate rigorously
    raw_candidates = [
        0.0,
        d_clearance * 0.5,
        d_clearance,
        d_expiry * 0.5,
        d_expiry,
        max(d_clearance, d_expiry) * 0.25,
        max(d_clearance, d_expiry) * 0.50,
        max(d_clearance, d_expiry) * 0.75,
        max(d_clearance, d_expiry),
        effective_max_discount,
    ]
    candidate_discounts = sorted(
        list(set(round(d, 4) for d in raw_candidates if 0.0 <= d <= effective_max_discount))
    )

    best_discount = 0.0
    best_price = regular_price
    best_profit = base_net_profit
    best_waste = base_waste
    action_reason = (
        "Retained regular price: inventory clears naturally"
        if coverage_ratio <= 1.0
        else "Retained regular price: markdown would reduce net profit (elasticity insufficient to offset price drop)"
    )

    for cand_d in candidate_discounts:
        if cand_d <= 0.001:
            continue
        cand_price = round(regular_price * (1.0 - cand_d), 2)
        if cand_price < min_allowable_price:
            continue
        effective_cand_d = round((regular_price - cand_price) / regular_price, 4)

        cand_daily_demand = calculate_demand_response(
            daily_demand,
            effective_cand_d,
            abs_elasticity,
            config.max_demand_multiplier,
        )
        cand_total_demand = cand_daily_demand * days_to_expiry
        cand_sold = min(float(initial_stock), cand_total_demand)
        cand_rev = round(cand_sold * cand_price, 2)
        cand_profit = round(cand_rev - total_inventory_cost, 2)
        cand_waste = initial_stock - cand_sold

        # Strictly compare with baseline profit using identical inventory cost
        if cand_profit > best_profit + 0.05:
            best_profit = cand_profit
            best_discount = effective_cand_d
            best_price = cand_price
            best_waste = cand_waste
            if base_net_profit < 0.0:
                action_reason = (
                    f"Applied {effective_cand_d:.1%} discount: mitigates batch spoilage loss "
                    f"(net profit: INR {base_net_profit:,.2f} -> INR {best_profit:,.2f})"
                )
            else:
                action_reason = (
                    f"Applied {effective_cand_d:.1%} discount: clears excess stock and increases net profit "
                    f"(net profit: INR {base_net_profit:,.2f} -> INR {best_profit:,.2f})"
                )
        elif abs(cand_profit - best_profit) <= 0.05 and cand_waste < best_waste - 0.1:
            best_profit = cand_profit
            best_discount = effective_cand_d
            best_price = cand_price
            best_waste = cand_waste
            action_reason = (
                f"Applied {effective_cand_d:.1%} discount: eliminates {base_waste - cand_waste:.1f} "
                f"units of waste with net profit parity"
            )

    # Hard enforcement of price floor
    if best_price < min_allowable_price:
        best_price = min_allowable_price
        best_discount = round((regular_price - best_price) / regular_price, 4)

    return best_price, best_discount, action_reason


def recommend_graduated_markdown_price(
    base_price: float,
    unit_cost: float,
    days_to_expiry: int,
    shelf_life_days: int = 7,
    near_expiry_threshold: int = 2,
    near_expiry_discount_pct: float = 0.20,
    urgent_clearance_threshold: int = 1,
    urgent_clearance_discount_pct: float = 0.40,
    min_gross_margin_pct: float = 0.0,
    enforce_margin_floor: bool = True,
) -> Tuple[float, float, str, bool]:
    """Recommend graduated near-expiry markdown price with margin floor enforcement.

    Implements the two-tier shelf-life aware clearance discount rules:
    - Urgent clearance: urgent_clearance_threshold (default 1 day), urgent_clearance_discount_pct (default 40%)
    - Near-expiry markdown: near_expiry_threshold (default 2 days), near_expiry_discount_pct (default 20%)
    - Urgent clearance takes precedence over near-expiry when both apply.
    - Never discounts expired products (days_to_expiry <= 0).
    - Selling price is bounded below by the minimum gross margin price floor:
      minimum_price = unit_cost / (1 - min_margin_rate).

    Parameters
    ----------
    base_price : float
        Regular retail catalog price in INR.
    unit_cost : float
        Wholesale unit acquisition cost in INR.
    days_to_expiry : int
        Days remaining until batch expiration.
    shelf_life_days : int, optional
        Total lifespan of the SKU (default 7).
    near_expiry_threshold : int, optional
        Threshold for first markdown (default 2 days).
    near_expiry_discount_pct : float, optional
        Discount fraction for first markdown (default 0.20 for 20%).
    urgent_clearance_threshold : int, optional
        Threshold for urgent clearance (default 1 day).
    urgent_clearance_discount_pct : float, optional
        Discount fraction for urgent clearance (default 0.40 for 40%).
    min_gross_margin_pct : float, optional
        Target minimum gross margin percentage (e.g. 10.0 for 10% margin floor).
    enforce_margin_floor : bool, optional
        Whether to enforce minimum gross margin floor (default True).

    Returns
    -------
    Tuple[float, float, str, bool]
        (selling_price, discount_fraction, reason, margin_floor_limited)
    """
    if days_to_expiry <= 0:
        return (base_price, 0.0, "Product expired; condemned as spoilage waste", False)

    # Shelf-life aware adjustment
    max_near_expiry_window = max(1, shelf_life_days - 2)
    eff_t2 = min(int(near_expiry_threshold), max_near_expiry_window)
    eff_t1 = min(int(urgent_clearance_threshold), eff_t2)

    # Precedence rule: urgent clearance takes priority over near-expiry
    if days_to_expiry <= eff_t1 and urgent_clearance_discount_pct > 0.0:
        raw_discount = float(urgent_clearance_discount_pct)
        reason = f"Urgent clearance (<= {eff_t1} day{'s' if eff_t1 != 1 else ''} to expiry)"
    elif days_to_expiry <= eff_t2 and near_expiry_discount_pct > 0.0:
        raw_discount = float(near_expiry_discount_pct)
        reason = f"Near-expiry markdown (<= {eff_t2} day{'s' if eff_t2 != 1 else ''} to expiry)"
    else:
        raw_discount = 0.0
        reason = "Sufficient shelf life remaining"

    if raw_discount <= 0.0:
        return (base_price, 0.0, reason, False)

    tentative_price = round(base_price * (1.0 - raw_discount), 2)

    # Calculate margin floor price: minimum_price = unit_cost / (1 - min_margin_rate)
    m = min_gross_margin_pct / 100.0 if min_gross_margin_pct > 1.0 else min_gross_margin_pct
    min_price = round(unit_cost / (1.0 - m), 2) if m > 0.0 else round(unit_cost, 2)

    if enforce_margin_floor and tentative_price < min_price:
        selling_price = min_price
        applied_discount = round((base_price - min_price) / base_price, 4)
        return (selling_price, applied_discount, f"{reason} (Capped at margin floor ₹{min_price:.2f})", True)
    else:
        return (tentative_price, raw_discount, reason, False)


def simulate_batch(
    row: pd.Series | Dict[str, Any],
    strategy: str = "dynamic",
    config: PricingPolicyConfig = PricingPolicyConfig(),
) -> BatchSimulationResult:
    """Simulate shelf-life sales and complete financial accounting for a single product batch.

    Parameters
    ----------
    row : pd.Series | Dict[str, Any]
        Row containing product-batch specifications.
    strategy : str, optional
        Pricing strategy: "fixed" or "dynamic", by default "dynamic".
    config : PricingPolicyConfig, optional
        Pricing policy parameters.

    Returns
    -------
    BatchSimulationResult
        Comprehensive performance and financial metrics for the batch.
    """
    initial_stock = int(row["initial_stock"])
    unit_cost = float(row["unit_cost"])
    regular_price = float(row["regular_price"])
    days_to_expiry = int(row["days_to_expiry"])
    daily_demand = float(row["daily_demand"])
    price_elasticity = float(row["price_elasticity"])

    if strategy.lower() == "fixed":
        selling_price = regular_price
        discount_pct = 0.0
        effective_daily_demand = max(0.0, daily_demand)
        limitation_reason = "Fixed-price baseline: standard regular price"
    elif strategy.lower() == "dynamic":
        selling_price, discount_pct, limitation_reason = recommend_dynamic_price(
            initial_stock=initial_stock,
            unit_cost=unit_cost,
            regular_price=regular_price,
            days_to_expiry=days_to_expiry,
            daily_demand=daily_demand,
            price_elasticity=price_elasticity,
            config=config,
        )
        effective_daily_demand = calculate_demand_response(
            baseline_demand=daily_demand,
            discount_pct=discount_pct,
            price_elasticity=price_elasticity,
            max_multiplier=config.max_demand_multiplier,
        )
    else:
        raise ValueError(f"Unknown strategy: '{strategy}'. Choose 'fixed' or 'dynamic'.")

    # Strictly deterministic expected sales calculation over remaining shelf life
    total_potential_demand = max(0.0, effective_daily_demand * max(0, days_to_expiry))
    units_sold = round(max(0.0, min(float(initial_stock), total_potential_demand)), 2)
    unsold_units = round(max(0.0, float(initial_stock) - units_sold), 2)

    # Financial Accounting (INR):
    # 1. Total Initial Inventory Cost: entire acquisition cost of the batch
    total_inventory_cost = round(float(initial_stock) * unit_cost, 2)

    # 2. Revenue: actual proceeds from units sold
    revenue = round(units_sold * selling_price, 2)

    # 3. Cost of Goods Sold (COGS): acquisition cost of units sold
    cogs = round(units_sold * unit_cost, 2)

    # 4. Gross Profit on sold units: revenue generated minus COGS
    gross_profit = round(revenue - cogs, 2)

    # 5. Waste Loss (spoilage cost): unrecoverable cost of expired unsold inventory
    # Reconciled to ensure COGS + Waste Loss == Total Inventory Cost exactly
    waste_loss = round(total_inventory_cost - cogs, 2)

    # 6. Net Retail Profit (Profit after inventory waste write-off)
    # Identical to Gross Profit - Waste Loss and Revenue - Total Inventory Cost
    net_profit = round(gross_profit - waste_loss, 2)

    waste_rate_pct = (
        round((unsold_units / float(initial_stock)) * 100.0, 2)
        if initial_stock > 0
        else 0.0
    )
    has_waste = unsold_units > 0.001

    return BatchSimulationResult(
        product_id=str(row["product_id"]),
        product_name=str(row["product_name"]),
        category=str(row["category"]),
        unit=str(row["unit"]),
        strategy=strategy.lower(),
        initial_stock=initial_stock,
        unit_cost=unit_cost,
        regular_price=regular_price,
        selling_price=selling_price,
        discount_pct=discount_pct,
        days_to_expiry=days_to_expiry,
        daily_demand=daily_demand,
        effective_daily_demand=effective_daily_demand,
        units_sold=units_sold,
        unsold_units=unsold_units,
        revenue=revenue,
        cogs=cogs,
        gross_profit=gross_profit,
        waste_loss=waste_loss,
        total_inventory_cost=total_inventory_cost,
        net_profit=net_profit,
        waste_rate_pct=waste_rate_pct,
        has_waste=has_waste,
        limitation_reason=limitation_reason,
    )


def simulate_inventory(
    df: pd.DataFrame,
    strategy: str = "dynamic",
    config: PricingPolicyConfig = PricingPolicyConfig(),
) -> pd.DataFrame:
    """Run shelf-life simulation across all batches in an inventory DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Inventory DataFrame.
    strategy : str, optional
        Pricing strategy ("fixed" or "dynamic"), by default "dynamic".
    config : PricingPolicyConfig, optional
        Pricing policy parameters.

    Returns
    -------
    pd.DataFrame
        Batch-level simulation results DataFrame.
    """
    records = []
    for _, row in df.iterrows():
        res = simulate_batch(row, strategy=strategy, config=config)
        d = asdict(res)
        # Add backward compatibility keys to DataFrame
        d["total_cost"] = res.total_inventory_cost
        d["waste_cost"] = res.waste_loss
        d["profit"] = res.net_profit
        records.append(d)
    return pd.DataFrame(records)


def compute_strategy_metrics(
    results_df: pd.DataFrame, strategy_name: str
) -> StrategyMetrics:
    """Compute aggregate business and reconciled financial metrics from batch results.

    Parameters
    ----------
    results_df : pd.DataFrame
        DataFrame of batch simulation results.
    strategy_name : str
        Name of strategy.

    Returns
    -------
    StrategyMetrics
        Aggregate metrics object reconciling physical units and financial totals.
    """
    total_batches = len(results_df)
    total_initial_stock = int(results_df["initial_stock"].sum())
    total_units_sold = round(float(results_df["units_sold"].sum()), 2)
    total_unsold_units = round(float(results_df["unsold_units"].sum()), 2)

    waste_rate_pct = (
        round((total_unsold_units / total_initial_stock) * 100.0, 2)
        if total_initial_stock > 0
        else 0.0
    )

    total_revenue = round(float(results_df["revenue"].sum()), 2)
    total_cogs = round(float(results_df["cogs"].sum()), 2)
    total_gross_profit = round(float(results_df["gross_profit"].sum()), 2)
    total_waste_loss = round(float(results_df["waste_loss"].sum()), 2)
    total_inventory_cost = round(float(results_df["total_inventory_cost"].sum()), 2)
    total_net_profit = round(float(results_df["net_profit"].sum()), 2)

    avg_discount_pct = (
        round(float(results_df["discount_pct"].mean()) * 100.0, 2)
        if total_batches > 0
        else 0.0
    )
    batches_with_waste = int((results_df["has_waste"]).sum())

    return StrategyMetrics(
        strategy_name=strategy_name,
        total_batches=total_batches,
        total_initial_stock=total_initial_stock,
        total_units_sold=total_units_sold,
        total_unsold_units=total_unsold_units,
        waste_rate_pct=waste_rate_pct,
        total_revenue=total_revenue,
        total_cogs=total_cogs,
        total_gross_profit=total_gross_profit,
        total_waste_loss=total_waste_loss,
        total_inventory_cost=total_inventory_cost,
        total_net_profit=total_net_profit,
        average_discount_pct=avg_discount_pct,
        batches_with_waste=batches_with_waste,
    )


def compare_strategies(
    df: pd.DataFrame,
    config: PricingPolicyConfig = PricingPolicyConfig(),
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare Fixed-Price Baseline and Dynamic-Pricing Strategy side-by-side.

    Uses identical initial inventory, costs, and baseline demand parameters.
    Reconciles physical inventory units and accounting totals mathematically.

    Parameters
    ----------
    df : pd.DataFrame
        Inventory DataFrame.
    config : PricingPolicyConfig, optional
        Pricing policy parameters.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
        (fixed_results_df, dynamic_results_df, comparison_summary_df)
    """
    fixed_results = simulate_inventory(df, strategy="fixed", config=config)
    dynamic_results = simulate_inventory(df, strategy="dynamic", config=config)

    fixed_metrics = compute_strategy_metrics(
        fixed_results, "Fixed-Price Baseline"
    )
    dynamic_metrics = compute_strategy_metrics(
        dynamic_results, "Dynamic Markdown Strategy"
    )

    rows = [
        # Physical Inventory Metrics
        {
            "Section": "Inventory Units",
            "Metric": "Total Batches Evaluated",
            "Fixed-Price Baseline": f"{fixed_metrics.total_batches:,}",
            "Dynamic Markdown Strategy": f"{dynamic_metrics.total_batches:,}",
            "Absolute Difference": f"{dynamic_metrics.total_batches - fixed_metrics.total_batches:+d}",
            "Percentage Change": "0.00%",
        },
        {
            "Section": "Inventory Units",
            "Metric": "Total Initial Stock (Units)",
            "Fixed-Price Baseline": f"{fixed_metrics.total_initial_stock:,}",
            "Dynamic Markdown Strategy": f"{dynamic_metrics.total_initial_stock:,}",
            "Absolute Difference": f"{dynamic_metrics.total_initial_stock - fixed_metrics.total_initial_stock:+d}",
            "Percentage Change": "0.00%",
        },
        {
            "Section": "Inventory Units",
            "Metric": "Expected Units Sold",
            "Fixed-Price Baseline": f"{fixed_metrics.total_units_sold:,.2f}",
            "Dynamic Markdown Strategy": f"{dynamic_metrics.total_units_sold:,.2f}",
            "Absolute Difference": f"{dynamic_metrics.total_units_sold - fixed_metrics.total_units_sold:+,.2f}",
            "Percentage Change": f"{((dynamic_metrics.total_units_sold - fixed_metrics.total_units_sold) / max(0.001, fixed_metrics.total_units_sold)) * 100.0:+.2f}%",
        },
        {
            "Section": "Inventory Units",
            "Metric": "Expected Unsold Units (Waste)",
            "Fixed-Price Baseline": f"{fixed_metrics.total_unsold_units:,.2f}",
            "Dynamic Markdown Strategy": f"{dynamic_metrics.total_unsold_units:,.2f}",
            "Absolute Difference": f"{dynamic_metrics.total_unsold_units - fixed_metrics.total_unsold_units:+,.2f}",
            "Percentage Change": f"{((dynamic_metrics.total_unsold_units - fixed_metrics.total_unsold_units) / max(0.001, fixed_metrics.total_unsold_units)) * 100.0:+.2f}%",
        },
        {
            "Section": "Inventory Units",
            "Metric": "Waste Rate (%)",
            "Fixed-Price Baseline": f"{fixed_metrics.waste_rate_pct:.2f}%",
            "Dynamic Markdown Strategy": f"{dynamic_metrics.waste_rate_pct:.2f}%",
            "Absolute Difference": f"{dynamic_metrics.waste_rate_pct - fixed_metrics.waste_rate_pct:+.2f}%",
            "Percentage Change": f"{((dynamic_metrics.waste_rate_pct - fixed_metrics.waste_rate_pct) / max(0.001, fixed_metrics.waste_rate_pct)) * 100.0:+.2f}%",
        },
        {
            "Section": "Inventory Units",
            "Metric": "Batches with Waste",
            "Fixed-Price Baseline": f"{fixed_metrics.batches_with_waste}",
            "Dynamic Markdown Strategy": f"{dynamic_metrics.batches_with_waste}",
            "Absolute Difference": f"{dynamic_metrics.batches_with_waste - fixed_metrics.batches_with_waste:+d}",
            "Percentage Change": f"{((dynamic_metrics.batches_with_waste - fixed_metrics.batches_with_waste) / max(0.001, fixed_metrics.batches_with_waste)) * 100.0:+.2f}%",
        },
        {
            "Section": "Pricing & Discounts",
            "Metric": "Average Markdown Discount (%)",
            "Fixed-Price Baseline": f"{fixed_metrics.average_discount_pct:.2f}%",
            "Dynamic Markdown Strategy": f"{dynamic_metrics.average_discount_pct:.2f}%",
            "Absolute Difference": f"{dynamic_metrics.average_discount_pct - fixed_metrics.average_discount_pct:+.2f}%",
            "Percentage Change": "N/A",
        },
        # Financial P&L Reconciliation
        {
            "Section": "Financial P&L (INR)",
            "Metric": "Total Revenue [Units Sold x Price]",
            "Fixed-Price Baseline": f"INR {fixed_metrics.total_revenue:,.2f}",
            "Dynamic Markdown Strategy": f"INR {dynamic_metrics.total_revenue:,.2f}",
            "Absolute Difference": f"INR {dynamic_metrics.total_revenue - fixed_metrics.total_revenue:+,.2f}",
            "Percentage Change": f"{((dynamic_metrics.total_revenue - fixed_metrics.total_revenue) / max(0.001, fixed_metrics.total_revenue)) * 100.0:+.2f}%",
        },
        {
            "Section": "Financial P&L (INR)",
            "Metric": "Cost of Goods Sold (COGS) [Units Sold x Cost]",
            "Fixed-Price Baseline": f"INR {fixed_metrics.total_cogs:,.2f}",
            "Dynamic Markdown Strategy": f"INR {dynamic_metrics.total_cogs:,.2f}",
            "Absolute Difference": f"INR {dynamic_metrics.total_cogs - fixed_metrics.total_cogs:+,.2f}",
            "Percentage Change": f"{((dynamic_metrics.total_cogs - fixed_metrics.total_cogs) / max(0.001, fixed_metrics.total_cogs)) * 100.0:+.2f}%",
        },
        {
            "Section": "Financial P&L (INR)",
            "Metric": "Gross Profit on Sold Units [Revenue - COGS]",
            "Fixed-Price Baseline": f"INR {fixed_metrics.total_gross_profit:,.2f}",
            "Dynamic Markdown Strategy": f"INR {dynamic_metrics.total_gross_profit:,.2f}",
            "Absolute Difference": f"INR {dynamic_metrics.total_gross_profit - fixed_metrics.total_gross_profit:+,.2f}",
            "Percentage Change": f"{((dynamic_metrics.total_gross_profit - fixed_metrics.total_gross_profit) / max(0.001, fixed_metrics.total_gross_profit)) * 100.0:+.2f}%",
        },
        {
            "Section": "Financial P&L (INR)",
            "Metric": "Waste Loss / Spoilage Cost [Unsold Units x Cost]",
            "Fixed-Price Baseline": f"INR {fixed_metrics.total_waste_loss:,.2f}",
            "Dynamic Markdown Strategy": f"INR {dynamic_metrics.total_waste_loss:,.2f}",
            "Absolute Difference": f"INR {dynamic_metrics.total_waste_loss - fixed_metrics.total_waste_loss:+,.2f}",
            "Percentage Change": f"{((dynamic_metrics.total_waste_loss - fixed_metrics.total_waste_loss) / max(0.001, fixed_metrics.total_waste_loss)) * 100.0:+.2f}%",
        },
        {
            "Section": "Financial P&L (INR)",
            "Metric": "Total Initial Inventory Cost [COGS + Waste Loss]",
            "Fixed-Price Baseline": f"INR {fixed_metrics.total_inventory_cost:,.2f}",
            "Dynamic Markdown Strategy": f"INR {dynamic_metrics.total_inventory_cost:,.2f}",
            "Absolute Difference": f"INR {dynamic_metrics.total_inventory_cost - fixed_metrics.total_inventory_cost:+,.2f}",
            "Percentage Change": "0.00%",
        },
        {
            "Section": "Financial P&L (INR)",
            "Metric": "Net Retail Profit [Gross Profit - Waste Loss]",
            "Fixed-Price Baseline": f"INR {fixed_metrics.total_net_profit:,.2f}",
            "Dynamic Markdown Strategy": f"INR {dynamic_metrics.total_net_profit:,.2f}",
            "Absolute Difference": f"INR {dynamic_metrics.total_net_profit - fixed_metrics.total_net_profit:+,.2f}",
            "Percentage Change": f"{((dynamic_metrics.total_net_profit - fixed_metrics.total_net_profit) / max(0.001, abs(fixed_metrics.total_net_profit))) * 100.0:+.2f}%",
        },
    ]

    summary_df = pd.DataFrame(rows)
    return fixed_results, dynamic_results, summary_df


def format_cli_report(summary_df: pd.DataFrame, dynamic_results: pd.DataFrame) -> str:
    """Format an informative ASCII comparison report for console presentation."""
    header = (
        "=" * 92 + "\n"
        "           FRESHPRICE AI - DYNAMIC PRICING & INVENTORY AUDIT REPORT\n"
        "  (Monetary figures in INR - Synthetic Indian Grocery Inventory Simulation)\n"
        "  Note: Sales figures are continuous expected values over each batch's shelf life.\n"
        + "=" * 92
    )

    summary_cols = ["Section", "Metric", "Fixed-Price Baseline", "Dynamic Markdown Strategy", "Absolute Difference", "Percentage Change"]
    summary_text = summary_df[summary_cols].to_string(index=False)

    # Highlighted batches that received markdown recommendations
    discounted = dynamic_results[dynamic_results["discount_pct"] > 0.001]
    if len(discounted) > 0:
        sample_cols = [
            "product_id",
            "product_name",
            "unit",
            "initial_stock",
            "unit_cost",
            "regular_price",
            "selling_price",
            "discount_pct",
            "units_sold",
            "unsold_units",
            "gross_profit",
            "waste_loss",
            "net_profit",
            "limitation_reason",
        ]
        sample_df = discounted[sample_cols].copy()
        sample_df["discount_pct"] = (sample_df["discount_pct"] * 100.0).round(1).astype(str) + "%"
        sample_text = (
            "\n" + "-" * 92 + "\n"
            f"  ACTIVE DYNAMIC MARKDOWN RECOMMENDATIONS ({len(discounted)} batches with discount > 0%)\n"
            "  * Note on Negative Net Profit: Occurs when Waste Loss on unsold units exceeds Gross Profit.\n"
            + "-" * 92 + "\n"
            + sample_df.to_string(index=False)
        )
    else:
        sample_text = "\nNo batches met conditions for profitable markdown."

    footer = "\n" + "=" * 92 + "\n"
    return f"{header}\n\n{summary_text}\n{sample_text}\n{footer}"


def main() -> None:
    """CLI entrypoint for running the pricing engine and printing the comparison report."""
    parser = argparse.ArgumentParser(
        description="FreshPrice AI - Dynamic Pricing Engine & Simulation (Phase 2)"
    )
    parser.add_argument(
        "--inventory",
        type=str,
        default=str(DEFAULT_INVENTORY_FILE),
        help=f"Path to synthetic inventory CSV (default: {DEFAULT_INVENTORY_FILE}).",
    )
    parser.add_argument(
        "--max-discount",
        type=float,
        default=0.40,
        help="Maximum allowed discount fraction (default: 0.40 for 40%%).",
    )
    parser.add_argument(
        "--output-summary",
        type=str,
        default=None,
        help="Optional path to save comparison summary table as CSV.",
    )

    args = parser.parse_args()

    config = PricingPolicyConfig(max_discount=args.max_discount)
    df = load_inventory(args.inventory)

    fixed_df, dynamic_df, summary_df = compare_strategies(df, config=config)
    report = format_cli_report(summary_df, dynamic_df)
    print(report)

    if args.output_summary:
        out_path = Path(args.output_summary).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(out_path, index=False)
        print(f"Comparison summary successfully saved to: {out_path}")


if __name__ == "__main__":
    main()
