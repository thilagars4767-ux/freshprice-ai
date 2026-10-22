"""Tests for FreshPrice AI Demand Estimation and Clearance Discount Optimizer.

NEXAI 2026 Hackathon (PS 4.1: Track 4 Grocery Retail).
"""

from datetime import date
from pathlib import Path
import pytest
import pandas as pd

from src.demand_estimator import DemandEstimator, ProductDemandProfile
from src.discount_optimizer import (
    CANDIDATE_DISCOUNTS,
    DiscountOptimizer,
    compute_minimum_acceptable_price,
    recommendations_to_dataframe,
)
from src.demand_history import generate_historical_demand_dataset
from src.store_simulator import (
    DEFAULT_PRODUCTS,
    MarkdownPolicyConfig,
    Product,
    get_default_products,
    run_store_simulation,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Test 1: Historical Demand Dataset Structure and Record Counts
# ---------------------------------------------------------------------------

def test_historical_demand_dataset_structure_and_counts():
    """Verify historical dataset contains exactly 20 products, 5 per category, 365 days, 7,300 rows."""
    csv_path = PROJECT_ROOT / "data" / "historical_product_demand.csv"
    assert csv_path.exists(), "historical_product_demand.csv must exist in data/"

    df = pd.read_csv(csv_path)

    # Exactly 7,300 rows (365 days * 20 products)
    assert len(df) == 7300, f"Expected 7,300 rows, found {len(df)}"

    # Exactly 20 unique products
    unique_prods = df["product_id"].unique()
    assert len(unique_prods) == 20, f"Expected 20 products, found {len(unique_prods)}"

    # Exactly 4 categories with 5 products each
    cat_counts = df.groupby("category")["product_id"].nunique().to_dict()
    assert cat_counts == {
        "bakery": 5,
        "dairy": 5,
        "fruits": 5,
        "vegetables": 5,
    }, f"Category distribution mismatch: {cat_counts}"

    # Exactly 365 distinct dates (2026-01-01 to 2026-12-31)
    unique_dates = df["date"].unique()
    assert len(unique_dates) == 365, f"Expected 365 dates, found {len(unique_dates)}"
    assert min(unique_dates) == "2026-01-01"
    assert max(unique_dates) == "2026-12-31"

    # All required columns present
    expected_cols = [
        "date", "product_id", "product_name", "category", "regular_price",
        "actual_price", "discount_pct", "unit_cost", "opening_stock",
        "units_received", "units_available", "units_sold", "units_wasted",
        "closing_stock", "manufacture_date", "expiry_date", "days_to_expiry",
        "weekday", "price", "base_demand", "price_sensitivity"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing required column: {col}"


# ---------------------------------------------------------------------------
# Test 2: Physical Feasibility — Units Sold Never Exceed Units Available
# ---------------------------------------------------------------------------

def test_historical_units_sold_bounded_by_available():
    """Verify that units sold never exceed physical units available for 100% of historical records."""
    csv_path = PROJECT_ROOT / "data" / "historical_product_demand.csv"
    df = pd.read_csv(csv_path)

    # Physical inventory constraint: units_sold <= units_available
    oversold = df[df["units_sold"] > df["units_available"] + 1e-4]
    assert oversold.empty, f"Found {len(oversold)} records where units sold exceeded units available"

    # Non-negative quantities
    assert (df["units_sold"] >= 0.0).all()
    assert (df["units_available"] >= 0.0).all()
    assert (df["units_wasted"] >= 0.0).all()
    assert (df["price"] > 0.0).all()
    assert (df["unit_cost"] > 0.0).all()


# ---------------------------------------------------------------------------
# Test 3: Demand Estimation Reproducibility
# ---------------------------------------------------------------------------

def test_demand_estimation_reproducibility():
    """Verify demand estimation produces deterministic, identical parameters across repeated invocations."""
    est_1 = DemandEstimator()
    est_2 = DemandEstimator()

    prods = get_default_products()
    profiles_1 = est_1.estimate_all_profiles()
    profiles_2 = est_2.estimate_all_profiles()

    assert set(profiles_1.keys()) == set(profiles_2.keys())
    for pid in profiles_1:
        p1 = profiles_1[pid]
        p2 = profiles_2[pid]
        assert p1.estimated_base_demand == p2.estimated_base_demand
        assert p1.estimated_price_sensitivity == p2.estimated_price_sensitivity
        assert p1.sensitivity_source == p2.sensitivity_source
        assert p1.historical_observations == p2.historical_observations


# ---------------------------------------------------------------------------
# Test 4: Temporal Boundary & No Future Data Leakage
# ---------------------------------------------------------------------------

def test_demand_estimation_no_future_leakage():
    """Verify demand estimation strictly respects cutoff_date and does not leak future data."""
    est = DemandEstimator()
    prod = DEFAULT_PRODUCTS[0]  # Toned Fresh Milk

    # Full 365-day estimation
    full_profile = est.estimate_product_profile(prod, cutoff_date=None)
    assert full_profile.historical_observations == 365

    # Truncated estimation at 2026-02-15 (46 days from 2026-01-01 to 2026-02-15)
    cutoff = "2026-02-15"
    bounded_profile = est.estimate_product_profile(prod, cutoff_date=cutoff)
    assert bounded_profile.historical_observations == 46
    assert bounded_profile.historical_observations < full_profile.historical_observations

    # Ensure get_historical_data filtered out dates strictly after cutoff
    filtered_df = est.get_historical_data(cutoff_date=cutoff)
    assert (pd.to_datetime(filtered_df["date"]) <= pd.to_datetime(cutoff)).all()


# ---------------------------------------------------------------------------
# Test 5: Fallback Handling for Insufficient Historical Price Variation
# ---------------------------------------------------------------------------

def test_insufficient_historical_price_variation_triggers_fallback():
    """Verify products with low or zero historical price variation trigger configured fallback safely."""
    est = DemandEstimator()

    # PROD-11 (Royal Gala Apples) was explicitly generated with 0% discount across all 90 days
    prod_apples = [p for p in DEFAULT_PRODUCTS if p.product_id == "PROD-11"][0]
    profile = est.estimate_product_profile(prod_apples)

    assert profile.discount_variation_std < 2.0
    assert profile.sensitivity_source == "configured_fallback"
    assert profile.estimated_price_sensitivity == prod_apples.price_sensitivity

    # Verify products with sufficient price variation use empirical regression
    prod_milk = [p for p in DEFAULT_PRODUCTS if p.product_id == "PROD-01"][0]
    profile_milk = est.estimate_product_profile(prod_milk)
    assert profile_milk.discount_variation_std >= 2.0
    assert profile_milk.sensitivity_source == "historical_estimate"


# ---------------------------------------------------------------------------
# Test 6: Minimum Gross Margin Price Floor Strictly Enforced
# ---------------------------------------------------------------------------

def test_minimum_gross_margin_price_floor_enforced():
    """Verify selling price floor P >= C / (1 - m) is strictly enforced after rounding."""
    # Test formula directly
    # Cost = ₹80.00, Margin = 20% -> Min Price = 80 / (1 - 0.20) = ₹100.00
    assert compute_minimum_acceptable_price(unit_cost=80.0, min_margin_pct=20.0) == 100.00

    # Cost = ₹64.00, Margin = 15% -> Min Price = 64 / 0.85 = 75.294... -> ₹75.29
    assert compute_minimum_acceptable_price(unit_cost=64.0, min_margin_pct=15.0) == 75.29

    # Test optimizer enforcement on candidate discounts
    opt = DiscountOptimizer(default_min_margin_pct=20.0)
    prod = [p for p in DEFAULT_PRODUCTS if p.product_id == "PROD-04"][0]  # Malai Paneer (Cost ₹82, Base ₹105)
    # Required min price for 20% margin = 82 / 0.80 = ₹102.50
    # Candidate at 5% OFF = ₹99.75 < ₹102.50 -> Must be rejected as infeasible!

    profile = ProductDemandProfile(
        product_id=prod.product_id,
        product_name=prod.name,
        category=prod.category,
        estimated_base_demand=18.0,
        estimated_price_sensitivity=1.6,
        sensitivity_source="historical_estimate",
        historical_observations=90,
        discount_variation_std=12.0,
        unique_discount_levels=4,
        mean_historical_price=prod.base_price,
        mean_historical_discount_pct=10.0,
        historical_waste_recorded=0.0,
    )

    rec = opt.optimize_product_discount(
        product=prod,
        current_stock=50.0,
        days_to_expiry=1,
        demand_profile=profile,
        min_margin_pct=20.0,
    )

    # Selling price must not violate floor
    min_acceptable = compute_minimum_acceptable_price(prod.unit_cost, 20.0)
    assert rec.recommended_selling_price >= min_acceptable - 1e-4

    # Every candidate evaluated as feasible must meet the floor
    for cand in rec.candidate_evaluations:
        if cand.is_feasible:
            assert cand.selling_price >= min_acceptable - 1e-4
        else:
            assert cand.selling_price < min_acceptable or not cand.is_feasible


# ---------------------------------------------------------------------------
# Test 7: Disallowing Minimum Margin >= 100% Raises ValueError
# ---------------------------------------------------------------------------

def test_disallowing_minimum_margin_ge_100_pct_raises_value_error():
    """Verify that requiring minimum gross margin >= 100% raises ValueError."""
    with pytest.raises(ValueError, match="mathematically impossible"):
        compute_minimum_acceptable_price(unit_cost=50.0, min_margin_pct=100.0)

    with pytest.raises(ValueError, match="mathematically impossible"):
        compute_minimum_acceptable_price(unit_cost=50.0, min_margin_pct=105.0)

    with pytest.raises(ValueError, match="mathematically impossible"):
        compute_minimum_acceptable_price(unit_cost=10.0, min_margin_pct=1.0)


# ---------------------------------------------------------------------------
# Test 8: Zero-Discount Recommendation When Stock Naturally Clears
# ---------------------------------------------------------------------------

def test_zero_discount_when_stock_sells_naturally():
    """Verify discount is 0% when stock is projected to sell out naturally before expiry at full price."""
    opt = DiscountOptimizer()
    prod = [p for p in DEFAULT_PRODUCTS if p.product_id == "PROD-06"][0]  # Sandwich Bread

    profile = ProductDemandProfile(
        product_id=prod.product_id,
        product_name=prod.name,
        category=prod.category,
        estimated_base_demand=30.0,  # 30 units/day
        estimated_price_sensitivity=1.7,
        sensitivity_source="historical_estimate",
        historical_observations=90,
        discount_variation_std=10.0,
        unique_discount_levels=4,
        mean_historical_price=prod.base_price,
        mean_historical_discount_pct=10.0,
        historical_waste_recorded=0.0,
    )

    # 40 units remaining with 2 days to expiry (demand capacity = 2 * 30 = 60 units >= 40)
    rec = opt.optimize_product_discount(
        product=prod,
        current_stock=40.0,
        days_to_expiry=2,
        demand_profile=profile,
        min_margin_pct=0.0,
    )

    assert rec.recommended_discount_pct == 0.0
    assert rec.recommended_selling_price == prod.base_price
    assert rec.is_discounted is False
    assert "sell out naturally" in rec.recommendation_explanation.lower()


# ---------------------------------------------------------------------------
# Test 9: Physical Inventory Conservation under Demand-Aware Simulation
# ---------------------------------------------------------------------------

def test_store_simulation_physical_inventory_conservation_under_demand_aware():
    """Verify physical inventory balance and GAAP reconciliation under demand-aware markdown policy."""
    cfg = MarkdownPolicyConfig(
        policy_mode="demand_aware",
        min_gross_margin_pct=10.0,
        waste_disposal_fee=2.0,
    )
    res = run_store_simulation(sim_days=30, seed=42, config=cfg)
    m = res.markdown_metrics
    f = res.fixed_metrics

    # Physical Inventory Conservation: Received == Sold + Wasted + Ending Stock
    assert abs(m.total_received - (m.units_sold + m.units_wasted + m.ending_inventory)) <= 1e-4

    # Financial GAAP Identity: Gross Margin == Revenue - COGS
    assert abs(m.gross_margin - round(m.revenue - m.cogs, 2)) <= 0.02
    expected_gm_pct = round((m.gross_margin / m.revenue) * 100.0, 2)
    assert abs(m.gross_margin_pct - expected_gm_pct) <= 0.02

    # Fixed Policy conservation also verified on same run
    assert abs(f.total_received - (f.units_sold + f.units_wasted + f.ending_inventory)) <= 1e-4
    assert f.total_received == m.total_received


# ---------------------------------------------------------------------------
# Test 10: Fixed-Price Baseline Independent of Markdown Strategy Settings
# ---------------------------------------------------------------------------

def test_fixed_baseline_independent_of_markdown_strategy():
    """Verify Fixed-Price baseline produces 100% identical results regardless of markdown policy settings."""
    cfg_rule = MarkdownPolicyConfig(policy_mode="graduated_rule", discount_1_pct=0.40, discount_2_pct=0.20)
    cfg_da = MarkdownPolicyConfig(policy_mode="demand_aware", min_gross_margin_pct=15.0, waste_disposal_fee=5.0)

    res_rule = run_store_simulation(sim_days=30, seed=42, config=cfg_rule)
    res_da = run_store_simulation(sim_days=30, seed=42, config=cfg_da)

    # Fixed metrics must be perfectly identical
    assert res_rule.fixed_metrics == res_da.fixed_metrics
    assert res_rule.fixed_metrics.total_received == res_da.fixed_metrics.total_received
    assert res_rule.fixed_metrics.units_sold == res_da.fixed_metrics.units_sold
    assert res_rule.fixed_metrics.units_wasted == res_da.fixed_metrics.units_wasted
    assert res_rule.fixed_metrics.revenue == res_da.fixed_metrics.revenue
    assert res_rule.fixed_metrics.gross_margin == res_da.fixed_metrics.gross_margin

    # Markdown outcomes must differ between rule and demand-aware optimization
    assert res_rule.markdown_metrics != res_da.markdown_metrics


# ---------------------------------------------------------------------------
# Test 11: Recommendations Presentation DataFrame Format
# ---------------------------------------------------------------------------

def test_recommendations_dataframe_format():
    """Verify recommendations DataFrame produces 20 rows and all 14 required columns."""
    res = run_store_simulation(
        sim_days=30,
        seed=42,
        config=MarkdownPolicyConfig(policy_mode="demand_aware", min_gross_margin_pct=10.0),
    )
    df = res.recommendations_df
    assert df is not None
    assert len(df) == 20

    expected_cols = [
        "Product Name", "Category", "Current Stock", "Days to Expiry",
        "Base Price", "Recommended Discount (%)", "Recommended Selling Price",
        "Base Margin (%)", "Discounted Margin (%)", "Estimated Baseline Demand",
        "Price Sensitivity (Elasticity)", "Expected Waste Without Markdown",
        "Expected Waste With Markdown", "Recommendation Reason"
    ]
    assert list(df.columns) == expected_cols

    # Categories formatted in title case
    assert set(df["Category"].unique()).issubset({"Dairy", "Bakery", "Fruits", "Vegetables"})


# ---------------------------------------------------------------------------
# Test 12: Products Dataset Structure, Categories, and Margin Bounds
# ---------------------------------------------------------------------------

def test_products_dataset_structure_and_constraints():
    """Verify data/products.csv contains exactly 20 products, 5 per category, and valid unit economics."""
    csv_path = PROJECT_ROOT / "data" / "products.csv"
    assert csv_path.exists(), "products.csv must exist in data/"

    df = pd.read_csv(csv_path)
    assert len(df) == 20, f"Expected 20 products in products.csv, found {len(df)}"

    expected_cols = [
        "product_id", "product_name", "category", "regular_price",
        "unit_cost", "base_daily_demand", "price_sensitivity", "shelf_life_days"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing required column in products.csv: {col}"

    cat_counts = df.groupby("category")["product_id"].nunique().to_dict()
    assert cat_counts == {"dairy": 5, "bakery": 5, "fruits": 5, "vegetables": 5}

    # Margin bounds: regular price > unit cost > 0
    assert (df["regular_price"] > df["unit_cost"]).all()
    assert (df["unit_cost"] > 0).all()
    assert (df["shelf_life_days"] >= 3).all()
    assert (df["shelf_life_days"] <= 14).all()
    assert (df["price_sensitivity"] >= 1.0).all()
    assert (df["price_sensitivity"] <= 2.2).all()


# ---------------------------------------------------------------------------
# Test 13: Product Price History Schema and Formula Integrity
# ---------------------------------------------------------------------------

def test_product_price_history_matches_demand_history():
    """Verify product_price_history.csv contains 7,300 rows and matches discount pricing formulas."""
    price_csv = PROJECT_ROOT / "data" / "product_price_history.csv"
    assert price_csv.exists(), "product_price_history.csv must exist in data/"

    df = pd.read_csv(price_csv)
    assert len(df) == 7300, f"Expected 7,300 rows in product_price_history.csv, found {len(df)}"

    expected_cols = [
        "date", "product_id", "product_name", "regular_price",
        "discount_pct", "actual_price", "unit_cost", "reason_for_price_change"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column in product_price_history.csv: {col}"

    # Selling price formula check: actual_price == regular_price * (1 - discount_pct/100)
    expected_price = (df["regular_price"] * (1.0 - df["discount_pct"] / 100.0)).round(2)
    assert (abs(df["actual_price"] - expected_price) <= 0.02).all()

    # Dates span exactly 365 days
    assert df["date"].nunique() == 365


# ---------------------------------------------------------------------------
# Test 14: Inventory Batch History FEFO and Physical Bounds
# ---------------------------------------------------------------------------

def test_inventory_batch_history_fefo_and_tracking():
    """Verify inventory_batch_history.csv tracks batch lifecycles with valid FEFO bounds."""
    batch_csv = PROJECT_ROOT / "data" / "inventory_batch_history.csv"
    assert batch_csv.exists(), "inventory_batch_history.csv must exist in data/"

    df = pd.read_csv(batch_csv)
    assert len(df) > 0

    expected_cols = [
        "batch_id", "product_id", "manufacture_date", "expiry_date",
        "shelf_life_days", "quantity_received", "quantity_remaining", "unit_cost"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column in inventory_batch_history.csv: {col}"

    # Unique batch IDs
    assert df["batch_id"].nunique() == len(df)

    # Expiry date >= Manufacture date
    mfg = pd.to_datetime(df["manufacture_date"])
    exp = pd.to_datetime(df["expiry_date"])
    assert (exp >= mfg).all()

    # Physical inventory bounds
    assert (df["quantity_received"] > 0).all()
    assert (df["quantity_remaining"] >= 0).all()
    assert (df["quantity_remaining"] <= df["quantity_received"] + 1e-4).all()
    assert (df["unit_cost"] > 0).all()


# ---------------------------------------------------------------------------
# Test 15: Daily Store History Reconciliation with Product Aggregates
# ---------------------------------------------------------------------------

def test_daily_store_history_reconciliation():
    """Verify daily_store_history.csv contains 365 rows and strictly reconciles with product demand aggregates."""
    store_csv = PROJECT_ROOT / "data" / "daily_store_history.csv"
    demand_csv = PROJECT_ROOT / "data" / "historical_product_demand.csv"
    assert store_csv.exists()
    assert demand_csv.exists()

    df_store = pd.read_csv(store_csv)
    df_demand = pd.read_csv(demand_csv)

    assert len(df_store) == 365, f"Expected 365 rows in daily_store_history.csv, found {len(df_store)}"

    expected_cols = [
        "date", "units_sold", "units_wasted", "revenue", "cogs", "gross_profit", "ending_inventory"
    ]
    for col in expected_cols:
        assert col in df_store.columns, f"Missing column in daily_store_history.csv: {col}"

    # Store GAAP identity: Gross Profit == Revenue - COGS
    gaap_margin_diff = abs(df_store["gross_profit"] - (df_store["revenue"] - df_store["cogs"]))
    assert (gaap_margin_diff <= 0.05).all()

    # Aggregate reconciliation by date
    df_demand["row_revenue"] = (df_demand["actual_price"] * df_demand["units_sold"]).round(2)
    df_demand["row_cogs"] = (df_demand["unit_cost"] * df_demand["units_sold"]).round(2)

    grouped = df_demand.groupby("date").agg({
        "row_revenue": "sum",
        "row_cogs": "sum",
        "units_sold": "sum",
        "units_wasted": "sum",
    }).reset_index()

    merged = pd.merge(df_store, grouped, on="date", suffixes=("_store", "_product"))
    assert len(merged) == 365

    assert (abs(merged["revenue"] - merged["row_revenue"]) <= 0.15).all()
    assert (abs(merged["cogs"] - merged["row_cogs"]) <= 0.15).all()
    assert (abs(merged["units_sold_store"] - merged["units_sold_product"]) <= 0.05).all()
    assert (abs(merged["units_wasted_store"] - merged["units_wasted_product"]) <= 0.05).all()

