"""Unit tests for FreshPrice AI Dynamic Pricing Engine (Phase 2)."""

from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.pricing_engine import (
    DEFAULT_INVENTORY_FILE,
    PricingPolicyConfig,
    calculate_demand_response,
    compare_strategies,
    load_inventory,
    recommend_dynamic_price,
    recommend_graduated_markdown_price,
    simulate_batch,
    simulate_inventory,
)


@pytest.fixture
def sample_inventory():
    """Load default 120-record synthetic grocery dataset."""
    return load_inventory(DEFAULT_INVENTORY_FILE)


def test_pricing_rule_never_below_unit_cost(sample_inventory):
    """Verify selling price is NEVER recommended below unit_cost across any batch."""
    config = PricingPolicyConfig(max_discount=0.50)
    results = simulate_inventory(sample_inventory, strategy="dynamic", config=config)

    # Every single batch must satisfy selling_price >= unit_cost
    assert (results["selling_price"] >= results["unit_cost"] - 0.001).all()

    # Synthetic stress-test: batch with extreme inventory surplus and near expiry
    price, discount, reason = recommend_dynamic_price(
        initial_stock=1000,
        unit_cost=50.0,
        regular_price=55.0,  # Only ₹5 margin
        days_to_expiry=1,
        daily_demand=10.0,
        price_elasticity=-2.5,
        config=config,
    )
    assert price >= 50.0
    assert discount <= (55.0 - 50.0) / 55.0 + 0.001


def test_pricing_rule_max_discount_cap():
    """Verify discount never exceeds configurable max_discount cap."""
    config = PricingPolicyConfig(max_discount=0.25)
    # Huge margin, high surplus, 1 day left: wants high discount, but capped at 25%
    price, discount, reason = recommend_dynamic_price(
        initial_stock=500,
        unit_cost=20.0,
        regular_price=100.0,  # 80% margin
        days_to_expiry=1,
        daily_demand=10.0,
        price_elasticity=-2.0,
        config=config,
    )
    assert discount <= 0.25 + 0.001
    assert price >= 75.0


def test_limitation_reported_when_markdown_not_possible():
    """Verify that when no profitable markdown is possible, regular price is retained and reason reported."""
    config = PricingPolicyConfig()

    # Case A: regular price equals unit cost (zero margin)
    price, discount, reason = recommend_dynamic_price(
        initial_stock=50,
        unit_cost=60.0,
        regular_price=60.0,
        days_to_expiry=1,
        daily_demand=10.0,
        price_elasticity=-1.5,
        config=config,
    )
    assert price == 60.0
    assert discount == 0.0
    assert "Price floor constraint" in reason

    # Case B: regular price below unit cost
    price_b, discount_b, reason_b = recommend_dynamic_price(
        initial_stock=50,
        unit_cost=70.0,
        regular_price=60.0,
        days_to_expiry=1,
        daily_demand=10.0,
        price_elasticity=-1.5,
        config=config,
    )
    assert price_b == 60.0
    assert discount_b == 0.0
    assert "Price floor constraint" in reason_b


def test_inventory_conservation_and_bounds(sample_inventory):
    """Verify inventory physical bounds: sold <= stock, unsold >= 0, and sold + unsold == stock."""
    fixed_res = simulate_inventory(sample_inventory, strategy="fixed")
    dynamic_res = simulate_inventory(sample_inventory, strategy="dynamic")

    for df in [fixed_res, dynamic_res]:
        # 1. No negative sales or negative stock
        assert (df["units_sold"] >= 0.0).all()
        assert (df["unsold_units"] >= 0.0).all()

        # 2. Sales can never exceed initial stock
        assert (df["units_sold"] <= df["initial_stock"] + 0.001).all()

        # 3. Exact conservation of inventory: units_sold + unsold_units == initial_stock
        stock_sum = (df["units_sold"] + df["unsold_units"]).round(2)
        assert (stock_sum == df["initial_stock"].round(2)).all()


def test_financial_accounting_identities(sample_inventory):
    """Verify all 5 core retail accounting identities hold exactly per batch."""
    for strategy in ["fixed", "dynamic"]:
        results = simulate_inventory(sample_inventory, strategy=strategy)

        for _, row in results.iterrows():
            # Identity 1: Revenue = units_sold * selling_price
            expected_rev = round(row["units_sold"] * row["selling_price"], 2)
            assert abs(row["revenue"] - expected_rev) <= 0.02

            # Identity 2: COGS = units_sold * unit_cost
            expected_cogs = round(row["units_sold"] * row["unit_cost"], 2)
            assert abs(row["cogs"] - expected_cogs) <= 0.02

            # Identity 3: Gross Profit = Revenue - COGS
            expected_gross_profit = round(row["revenue"] - row["cogs"], 2)
            assert abs(row["gross_profit"] - expected_gross_profit) <= 0.02

            # Identity 4: Total Inventory Cost = COGS + Waste Loss
            cogs_plus_waste = round(row["cogs"] + row["waste_loss"], 2)
            assert abs(row["total_inventory_cost"] - cogs_plus_waste) <= 0.02

            # Identity 5: Net Profit = Gross Profit - Waste Loss == Revenue - Total Inventory Cost
            expected_net_from_gross = round(row["gross_profit"] - row["waste_loss"], 2)
            expected_net_from_rev = round(row["revenue"] - row["total_inventory_cost"], 2)
            assert abs(row["net_profit"] - expected_net_from_gross) <= 0.02
            assert abs(row["net_profit"] - expected_net_from_rev) <= 0.02


def test_positive_margin_with_negative_net_profit_audit(sample_inventory):
    """Investigate and verify why batches with selling_price > unit_cost can have net_profit < 0.

    Root Cause:
    When a batch has high initial excess stock that expires unsold, the unrecoverable
    spoilage cost (Waste Loss) exceeds the gross profit earned on the units sold.
    Gross profit is positive, but net profit after inventory waste is negative.
    """
    results = simulate_inventory(sample_inventory, strategy="dynamic")

    # Find batches where selling margin is strictly positive but net profit is negative
    loss_batches = results[
        (results["selling_price"] > results["unit_cost"]) & (results["net_profit"] < 0)
    ]

    assert len(loss_batches) > 0, "Expected at least one overstocked batch with negative net profit."

    for _, row in loss_batches.iterrows():
        # 1. Selling margin is positive
        assert row["selling_price"] > row["unit_cost"]

        # 2. Gross profit on sold units is positive
        assert row["gross_profit"] > 0.0

        # 3. Waste loss from expired units strictly exceeds gross profit
        assert row["waste_loss"] > row["gross_profit"]

        # 4. Net profit equals gross_profit - waste_loss < 0
        assert row["net_profit"] == round(row["gross_profit"] - row["waste_loss"], 2)


def test_markdown_profitability_guarantee(sample_inventory):
    """Verify that whenever dynamic pricing applies a discount, dynamic net profit >= fixed net profit."""
    fixed_res, dynamic_res, _ = compare_strategies(sample_inventory)

    for i in range(len(sample_inventory)):
        f_row = fixed_res.iloc[i]
        d_row = dynamic_res.iloc[i]

        if d_row["discount_pct"] > 0.001:
            # Dynamic pricing must not recommend a discount that produces lower net profit than baseline
            assert (
                d_row["net_profit"] >= f_row["net_profit"] - 0.10
            ), f"Batch {d_row['product_id']} discount produced lower net profit than fixed baseline."


def test_aggregate_financial_reconciliation(sample_inventory):
    """Verify aggregate summary metrics match the sum of individual batch results exactly."""
    fixed_res, dynamic_res, summary_df = compare_strategies(sample_inventory)

    # Reconcile Dynamic totals
    assert round(dynamic_res["revenue"].sum(), 2) == float(
        summary_df.loc[
            summary_df["Metric"].str.startswith("Total Revenue"),
            "Dynamic Markdown Strategy",
        ].values[0].replace("INR ", "").replace(",", "")
    )
    assert round(dynamic_res["cogs"].sum(), 2) == float(
        summary_df.loc[
            summary_df["Metric"].str.startswith("Cost of Goods Sold"),
            "Dynamic Markdown Strategy",
        ].values[0].replace("INR ", "").replace(",", "")
    )
    assert round(dynamic_res["gross_profit"].sum(), 2) == float(
        summary_df.loc[
            summary_df["Metric"].str.startswith("Gross Profit"),
            "Dynamic Markdown Strategy",
        ].values[0].replace("INR ", "").replace(",", "")
    )
    assert round(dynamic_res["waste_loss"].sum(), 2) == float(
        summary_df.loc[
            summary_df["Metric"].str.startswith("Waste Loss"),
            "Dynamic Markdown Strategy",
        ].values[0].replace("INR ", "").replace(",", "")
    )
    assert round(dynamic_res["net_profit"].sum(), 2) == float(
        summary_df.loc[
            summary_df["Metric"].str.startswith("Net Retail Profit"),
            "Dynamic Markdown Strategy",
        ].values[0].replace("INR ", "").replace(",", "")
    )


def test_waste_reduction_comparison(sample_inventory):
    """Verify that dynamic pricing reduces waste and waste rate vs fixed baseline."""
    fixed_res, dynamic_res, summary_df = compare_strategies(sample_inventory)

    fixed_waste = fixed_res["unsold_units"].sum()
    dynamic_waste = dynamic_res["unsold_units"].sum()

    # Dynamic pricing should stimulate demand and reduce waste
    assert dynamic_waste <= fixed_waste

    # Waste rate must match calculation
    total_stock = sample_inventory["initial_stock"].sum()
    reported_fixed_waste_rate = float(
        summary_df.loc[
            summary_df["Metric"] == "Waste Rate (%)", "Fixed-Price Baseline"
        ].values[0].replace("%", "")
    )
    assert abs((fixed_waste / total_stock) * 100.0 - reported_fixed_waste_rate) < 0.05


def test_deterministic_reproducibility(sample_inventory):
    """Verify that running the simulation multiple times yields identical results."""
    fixed_a, dyn_a, sum_a = compare_strategies(sample_inventory)
    fixed_b, dyn_b, sum_b = compare_strategies(sample_inventory)

    pd.testing.assert_frame_equal(fixed_a, fixed_b)
    pd.testing.assert_frame_equal(dyn_a, dyn_b)
    pd.testing.assert_frame_equal(sum_a, sum_b)


def test_edge_case_zero_demand():
    """Verify handling when daily_demand is zero."""
    dummy_row = {
        "product_id": "TEST-0001",
        "product_name": "Zero Demand Item",
        "category": "bakery",
        "unit": "per loaf",
        "initial_stock": 50,
        "unit_cost": 30.0,
        "regular_price": 45.0,
        "days_to_expiry": 3,
        "daily_demand": 0.0,
        "price_elasticity": -1.5,
    }
    res = simulate_batch(dummy_row, strategy="dynamic")
    assert res.units_sold == 0.0
    assert res.unsold_units == 50.0
    assert res.selling_price == 45.0
    assert res.revenue == 0.0
    assert res.gross_profit == 0.0
    assert res.waste_loss == 1500.0
    assert res.net_profit == -1500.0  # 50 * 30 loss


def test_edge_case_zero_initial_stock():
    """Verify handling when initial_stock is zero."""
    dummy_row = {
        "product_id": "TEST-0002",
        "product_name": "Out of Stock Item",
        "category": "dairy",
        "unit": "per litre",
        "initial_stock": 0,
        "unit_cost": 50.0,
        "regular_price": 60.0,
        "days_to_expiry": 2,
        "daily_demand": 25.0,
        "price_elasticity": -1.2,
    }
    res = simulate_batch(dummy_row, strategy="dynamic")
    assert res.units_sold == 0.0
    assert res.unsold_units == 0.0
    assert res.revenue == 0.0
    assert res.gross_profit == 0.0
    assert res.waste_loss == 0.0
    assert res.net_profit == 0.0
    assert res.waste_rate_pct == 0.0


def test_edge_case_one_day_to_expiry():
    """Verify expiry urgency markdown when 1 day is left and excess stock exists."""
    dummy_row = {
        "product_id": "TEST-0003",
        "product_name": "Expiring Tomorrow Item",
        "category": "bakery",
        "unit": "per loaf",
        "initial_stock": 40,
        "unit_cost": 30.0,
        "regular_price": 50.0,
        "days_to_expiry": 1,
        "daily_demand": 20.0,  # 20 units would expire!
        "price_elasticity": -1.8,
    }
    res_fixed = simulate_batch(dummy_row, strategy="fixed")
    res_dyn = simulate_batch(dummy_row, strategy="dynamic")

    assert res_fixed.unsold_units == 20.0
    # Dynamic markdown should increase demand and reduce unsold units
    assert res_dyn.discount_pct > 0.0
    assert res_dyn.unsold_units < res_fixed.unsold_units
    assert res_dyn.selling_price >= 30.0


def test_demand_response_equation():
    """Verify demand response formula and bounds."""
    # 1. Zero discount -> demand unchanged
    assert calculate_demand_response(20.0, 0.0, -1.5) == 20.0

    # 2. 10% discount with Ed = -1.5 -> +15% demand (20.0 * 1.15 = 23.0)
    assert calculate_demand_response(20.0, 0.10, -1.5) == 23.0

    # 3. Multiplier capping
    assert calculate_demand_response(20.0, 0.50, -5.0, max_multiplier=2.0) == 40.0


def test_cli_execution(tmp_path: Path):
    """Verify CLI interface runs and generates output file."""
    output_path = tmp_path / "comparison_summary.csv"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pricing_engine",
            "--max-discount",
            "0.35",
            "--output-summary",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0
    assert output_path.exists()
    df = pd.read_csv(output_path)
    assert "Metric" in df.columns
    assert "Fixed-Price Baseline" in df.columns
    assert "Dynamic Markdown Strategy" in df.columns


# ---------------------------------------------------------------------------
# Tests for Graduated Markdown Pricing Rules & Margin Floor Enforcement
# ---------------------------------------------------------------------------

def test_graduated_markdown_default_thresholds_produce_expected_prices():
    """Verify default thresholds (20% at 2 days, 40% at 1 day) calculate expected prices."""
    base_price = 100.0
    unit_cost = 40.0

    # 1. 2 days remaining -> 20% discount (Price: 80.0)
    p2, d2, reason2, limited2 = recommend_graduated_markdown_price(
        base_price=base_price,
        unit_cost=unit_cost,
        days_to_expiry=2,
        shelf_life_days=7,
        near_expiry_threshold=2,
        near_expiry_discount_pct=0.20,
        urgent_clearance_threshold=1,
        urgent_clearance_discount_pct=0.40,
    )
    assert p2 == 80.0
    assert d2 == 0.20
    assert "Near-expiry markdown" in reason2
    assert not limited2

    # 2. 1 day remaining -> 40% discount (Price: 60.0)
    p1, d1, reason1, limited1 = recommend_graduated_markdown_price(
        base_price=base_price,
        unit_cost=unit_cost,
        days_to_expiry=1,
        shelf_life_days=7,
        near_expiry_threshold=2,
        near_expiry_discount_pct=0.20,
        urgent_clearance_threshold=1,
        urgent_clearance_discount_pct=0.40,
    )
    assert p1 == 60.0
    assert d1 == 0.40
    assert "Urgent clearance" in reason1
    assert not limited1

    # 3. 3 days remaining -> 0% discount (Price: 100.0)
    p3, d3, reason3, limited3 = recommend_graduated_markdown_price(
        base_price=base_price,
        unit_cost=unit_cost,
        days_to_expiry=3,
        shelf_life_days=7,
    )
    assert p3 == 100.0
    assert d3 == 0.0
    assert "Sufficient shelf life" in reason3
    assert not limited3


def test_graduated_markdown_changing_thresholds_updates_prices():
    """Verify changing thresholds and discount rates directly adjusts pricing."""
    base_price = 200.0
    unit_cost = 80.0

    # Changing near-expiry threshold to 3 days and discount to 25%
    p, d, reason, _ = recommend_graduated_markdown_price(
        base_price=base_price,
        unit_cost=unit_cost,
        days_to_expiry=3,
        shelf_life_days=7,
        near_expiry_threshold=3,
        near_expiry_discount_pct=0.25,
        urgent_clearance_threshold=1,
        urgent_clearance_discount_pct=0.50,
    )
    assert p == 150.0  # 200 * (1 - 0.25)
    assert d == 0.25
    assert "Near-expiry markdown" in reason

    # Changing urgent clearance discount to 50%
    p_urg, d_urg, reason_urg, _ = recommend_graduated_markdown_price(
        base_price=base_price,
        unit_cost=unit_cost,
        days_to_expiry=1,
        shelf_life_days=7,
        near_expiry_threshold=3,
        near_expiry_discount_pct=0.25,
        urgent_clearance_threshold=1,
        urgent_clearance_discount_pct=0.50,
    )
    assert p_urg == 100.0  # 200 * (1 - 0.50)
    assert d_urg == 0.50
    assert "Urgent clearance" in reason_urg


def test_graduated_markdown_urgent_clearance_precedence():
    """Verify urgent clearance rule takes precedence over near-expiry when both apply."""
    # When days_to_expiry = 1, it satisfies both <= 1 (urgent) and <= 2 (near-expiry).
    p, d, reason, _ = recommend_graduated_markdown_price(
        base_price=100.0,
        unit_cost=30.0,
        days_to_expiry=1,
        shelf_life_days=7,
        near_expiry_threshold=2,
        near_expiry_discount_pct=0.20,
        urgent_clearance_threshold=1,
        urgent_clearance_discount_pct=0.40,
    )
    # Must apply 40% urgent clearance, NOT 20% near-expiry
    assert d == 0.40
    assert p == 60.0
    assert "Urgent clearance" in reason


def test_graduated_markdown_minimum_margin_floor_enforcement():
    """Verify minimum gross margin floor caps excessive markdowns."""
    base_price = 100.0
    unit_cost = 80.0  # High cost item

    # Tentative 40% discount would result in ₹60, which breaches unit_cost (₹80)
    # With min_gross_margin_pct = 10.0:
    # minimum_price = unit_cost / (1 - 0.10) = 80 / 0.90 = ₹88.89
    p, d, reason, limited = recommend_graduated_markdown_price(
        base_price=base_price,
        unit_cost=unit_cost,
        days_to_expiry=1,
        shelf_life_days=7,
        urgent_clearance_threshold=1,
        urgent_clearance_discount_pct=0.40,
        min_gross_margin_pct=10.0,
        enforce_margin_floor=True,
    )
    assert p == 88.89
    assert limited is True
    assert p >= unit_cost
    gross_margin_achieved = (p - unit_cost) / p
    assert gross_margin_achieved >= 0.099  # ~10% margin floor preserved
    assert "Capped at margin floor" in reason


def test_graduated_markdown_expired_products_never_discounted_or_sold():
    """Verify products with 0 or negative shelf life are rejected with zero discount."""
    for expired_days in [0, -1, -5]:
        p, d, reason, limited = recommend_graduated_markdown_price(
            base_price=50.0,
            unit_cost=30.0,
            days_to_expiry=expired_days,
            shelf_life_days=5,
        )
        assert p == 50.0
        assert d == 0.0
        assert "expired" in reason.lower()
        assert not limited

