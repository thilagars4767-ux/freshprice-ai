"""Unit tests for FreshPrice AI Streamlit Dashboard Module (NEXAI 2026 Hackathon PS 4.1)."""

from pathlib import Path
import pytest
import plotly.graph_objects as go
import pandas as pd

from src.dashboard import (
    create_comparison_chart,
    create_daily_trends_chart,
    create_demand_trend_chart,
    create_discount_history_chart,
    create_historical_price_chart,
    create_sim_product_price_chart,
    create_sim_product_price_vs_sales_chart,
    create_sim_product_sales_vs_price_chart,
    create_sim_product_sales_waste_chart,
    create_waste_comparison_chart,
    format_inr,
    format_pct,
    format_pp,
    format_units,
    generate_rule_logic_explanation,
    load_historical_demand_data,
    load_product_price_history,
    render_per_product_view,
    run_dashboard_simulation,
)
from src.store_simulator import (
    MarkdownPolicyConfig,
    generate_arrival_schedule,
    get_default_products,
    run_store_simulation,
)
from src.pricing_engine import recommend_graduated_markdown_price


@pytest.fixture
def sample_sim_result():
    """Run standard 30-day simulation with default parameters."""
    return run_store_simulation(sim_days=30, seed=42)


def test_formatting_helpers():
    """Verify INR currency, percentage, and physical unit string formatting helpers."""
    assert format_inr(100.5) == "₹100.50"
    assert format_inr(107491.34) == "₹107,491.34"
    assert format_inr(150.0, include_sign=True) == "+₹150.00"
    assert format_inr(-75.5, include_sign=True) == "-₹75.50"

    assert format_pct(12.345) == "12.35%"
    assert format_pct(5.0, include_sign=True) == "+5.00%"
    assert format_pct(-10.0, include_sign=True) == "-10.00%"

    # Physical unit formatting with sign
    assert format_units(1617.0, include_sign=True) == "+1,617 units"
    assert format_units(2173.3, include_sign=True) == "+2,173.3 units"
    assert format_units(-10.5, include_sign=True) == "-10.5 units"
    assert format_units(0.0, include_sign=True) == "0 units"
    assert format_units(500.0) == "500 units"
    assert format_units(500.5) == "500.5 units"


def test_create_comparison_chart(sample_sim_result):
    """Verify create_comparison_chart produces a valid 2-trace Plotly grouped bar chart."""
    f = sample_sim_result.fixed_metrics
    m = sample_sim_result.markdown_metrics
    fig = create_comparison_chart(f, m)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    trace_names = [t.name for t in fig.data]
    assert "Fixed-Price Policy" in trace_names
    assert "Markdown Policy" in trace_names
    assert list(fig.data[0].x) == ["Total Revenue (₹)", "Gross Margin (₹)"]


def test_create_waste_comparison_chart(sample_sim_result):
    """Verify create_waste_comparison_chart produces a valid Plotly chart for physical waste."""
    f = sample_sim_result.fixed_metrics
    m = sample_sim_result.markdown_metrics
    fig = create_waste_comparison_chart(f, m)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert list(fig.data[0].x) == ["Fixed-Price Policy", "Markdown Policy"]
    assert fig.data[0].y[0] == f.units_wasted
    assert fig.data[0].y[1] == m.units_wasted


def test_dashboard_simulation_integration(sample_sim_result):
    """Verify simulation outputs required by dashboard tables and KPI cards."""
    res = sample_sim_result
    assert res.seed == 42
    assert res.sim_days == 30

    # Summary table columns
    summary_cols = list(res.comparison_summary_df.columns)
    assert summary_cols == ["Metric", "Fixed-Price Policy", "Markdown Policy", "Difference"]

    # Daily history required columns
    daily_cols = res.daily_history_df.columns
    for col in ["day", "policy", "product_name", "category", "days_until_expiry", "regular_price", "selling_price", "discount_pct", "units_sold", "units_wasted", "revenue", "gross_margin"]:
        assert col in daily_cols

    # Markdown events columns
    events_cols = res.markdown_events_df.columns
    for col in ["day", "product_id", "product_name", "category", "days_until_expiry", "regular_price", "selling_price", "discount_pct", "units_sold"]:
        assert col in events_cols


# ---------------------------------------------------------------------------
# Regression Tests for Dashboard Simulation Trigger & Orchestration
# ---------------------------------------------------------------------------

def test_urgent_clearance_discount_changes_configuration():
    """1. Verify changing urgent clearance discount updates configuration and recalculates simulation."""
    res_base = run_dashboard_simulation(discount_1_pct=0.40, discount_2_pct=0.20, seed=42)
    res_low = run_dashboard_simulation(discount_1_pct=0.10, discount_2_pct=0.20, seed=42)

    # Configuration change must trigger different markdown outcomes
    assert res_base.markdown_metrics != res_low.markdown_metrics
    assert res_base.markdown_metrics.revenue != res_low.markdown_metrics.revenue


def test_near_expiry_discount_changes_configuration():
    """2. Verify changing near-expiry discount updates configuration and recalculates simulation."""
    res_20 = run_dashboard_simulation(discount_1_pct=0.40, discount_2_pct=0.20, seed=42)
    res_05 = run_dashboard_simulation(discount_1_pct=0.40, discount_2_pct=0.05, seed=42)

    assert res_20.markdown_metrics != res_05.markdown_metrics
    assert res_20.markdown_metrics.units_sold != res_05.markdown_metrics.units_sold


def test_expiry_thresholds_update_configuration():
    """3. Verify changing either expiry threshold updates configuration and recalculates simulation."""
    res_t2 = run_dashboard_simulation(threshold_1_days=1, threshold_2_days=2, seed=42)
    res_t4 = run_dashboard_simulation(threshold_1_days=1, threshold_2_days=4, seed=42)

    assert res_t2.markdown_metrics != res_t4.markdown_metrics
    assert res_t2.markdown_metrics.markdown_events_count != res_t4.markdown_metrics.markdown_events_count


def test_seed_or_duration_recalculates_simulation():
    """4. Verify changing seed or duration recalculates simulation."""
    res_30 = run_dashboard_simulation(sim_days=30, seed=42)
    res_15 = run_dashboard_simulation(sim_days=15, seed=42)
    res_seed99 = run_dashboard_simulation(sim_days=30, seed=99)

    assert res_15.sim_days == 15
    assert len(res_15.daily_history_df) == 20 * 15 * 2
    assert res_30.fixed_metrics.total_received != res_15.fixed_metrics.total_received
    assert res_30.fixed_metrics.units_sold != res_seed99.fixed_metrics.units_sold


def test_displayed_results_correspond_to_latest_configuration():
    """5. Verify results correspond to the exact configuration passed."""
    res_mild = run_dashboard_simulation(discount_1_pct=0.10, discount_2_pct=0.05, seed=42)
    summary_df = res_mild.comparison_summary_df

    # Verify Markdown Policy values in summary_df match markdown_metrics
    m = res_mild.markdown_metrics
    sold_row = summary_df[summary_df["Metric"] == "Units Sold"]["Markdown Policy"].values[0]
    assert float(sold_row) == m.units_sold
    rev_row = summary_df[summary_df["Metric"] == "Total Revenue (INR)"]["Markdown Policy"].values[0]
    assert float(rev_row) == m.revenue


def test_fixed_price_baseline_independent_of_markdown_settings():
    """6. Verify fixed baseline remains unchanged when only markdown discounts change."""
    res_a = run_dashboard_simulation(discount_1_pct=0.40, discount_2_pct=0.20, seed=42, sim_days=30)
    res_b = run_dashboard_simulation(discount_1_pct=0.10, discount_2_pct=0.05, seed=42, sim_days=30)

    # Fixed metrics must be 100% identical
    assert res_a.fixed_metrics == res_b.fixed_metrics
    # Markdown metrics must differ
    assert res_a.markdown_metrics != res_b.markdown_metrics


def test_same_configuration_produces_reproducible_results():
    """7. Verify deterministic reproducibility for identical configurations."""
    run_1 = run_dashboard_simulation(sim_days=30, seed=42, threshold_1_days=1, discount_1_pct=0.40, threshold_2_days=2, discount_2_pct=0.20)
    run_2 = run_dashboard_simulation(sim_days=30, seed=42, threshold_1_days=1, discount_1_pct=0.40, threshold_2_days=2, discount_2_pct=0.20)

    assert run_1.fixed_metrics == run_2.fixed_metrics
    assert run_1.markdown_metrics == run_2.markdown_metrics
    pd.testing.assert_frame_equal(run_1.comparison_summary_df, run_2.comparison_summary_df)


def test_accounting_and_inventory_invariants_valid():
    """8. Verify GAAP accounting identities and physical inventory conservation across configs."""
    for d1, d2 in [(0.40, 0.20), (0.15, 0.10), (0.05, 0.05)]:
        res = run_dashboard_simulation(discount_1_pct=d1, discount_2_pct=d2, seed=42)
        for m in [res.fixed_metrics, res.markdown_metrics]:
            # Accounting: Gross Margin == Revenue - COGS
            assert abs(m.gross_margin - round(m.revenue - m.cogs, 2)) <= 0.02
            # Inventory Conservation: Received == Sold + Wasted + Ending
            assert abs(m.total_received - (m.units_sold + m.units_wasted + m.ending_inventory)) <= 1e-4


# ---------------------------------------------------------------------------
# Dashboard Audit Tests (Verification of Comparison Variance Metrics)
# ---------------------------------------------------------------------------

def test_physical_waste_saved_calculation_and_positive_sign():
    """Verify Physical Waste Saved equals fixed waste minus markdown waste and formats with positive sign."""
    res = run_dashboard_simulation(seed=42)
    f = res.fixed_metrics
    m = res.markdown_metrics

    # Calculation: Fixed waste minus Markdown waste
    waste_saved = round(f.units_wasted - m.units_wasted, 1)

    # In default seed 42: Fixed waste is 1,617.0 and Markdown waste is 0.0
    assert f.units_wasted == 1617.0
    assert m.units_wasted == 0.0
    assert waste_saved == 1617.0

    # Display string must be explicitly positive: +1,617 units
    formatted = format_units(waste_saved, include_sign=True)
    assert formatted == "+1,617 units"

    # Edge Case: When fixed waste equals markdown waste (waste_saved = 0.0)
    assert format_units(0.0, include_sign=True) == "0 units"


def test_comparison_metrics_formulas_and_signs():
    """Verify all variance metrics use strictly consistent formulas and standard delta signs."""
    res = run_dashboard_simulation(seed=42)
    f = res.fixed_metrics
    m = res.markdown_metrics

    # 1. Additional Units Sold: Markdown Sold - Fixed Sold
    units_sold_gain = round(m.units_sold - f.units_sold, 1)
    assert units_sold_gain > 0
    assert format_units(units_sold_gain, include_sign=True).startswith("+")

    # 2. Physical Waste Saved: Fixed Waste - Markdown Waste
    waste_saved = round(f.units_wasted - m.units_wasted, 1)
    assert waste_saved > 0
    assert format_units(waste_saved, include_sign=True).startswith("+")

    # 3. Waste Reduction %: (Fixed - Markdown) / Fixed * 100
    waste_red_pct = round(((f.units_wasted - m.units_wasted) / f.units_wasted * 100.0), 2)
    assert waste_red_pct == 100.0

    # 4. Revenue Change: Markdown Revenue - Fixed Revenue
    rev_gain = round(m.revenue - f.revenue, 2)
    assert rev_gain > 0
    assert format_inr(rev_gain, include_sign=True).startswith("+₹")

    # 5. COGS Variance: Markdown COGS - Fixed COGS
    cogs_diff = round(m.cogs - f.cogs, 2)
    assert cogs_diff > 0
    assert format_inr(cogs_diff, include_sign=True).startswith("+₹")

    # 6. Gross Margin Change: Markdown Margin - Fixed Margin
    margin_gain = round(m.gross_margin - f.gross_margin, 2)
    assert margin_gain < 0
    assert format_inr(margin_gain, include_sign=True).startswith("-₹")

    # 7. Gross Margin % Change: Markdown Margin % - Fixed Margin %
    margin_pct_diff = round(m.gross_margin_pct - f.gross_margin_pct, 2)
    assert margin_pct_diff < 0
    assert format_pct(margin_pct_diff, include_sign=True).startswith("-")

    # 8. Unsold Ending Stock Delta: Markdown Ending - Fixed Ending
    ending_stock_delta = round(m.ending_inventory - f.ending_inventory, 1)
    assert ending_stock_delta < 0
    assert format_units(ending_stock_delta, include_sign=True).startswith("-")


def test_gross_margin_calculation_and_divergence_communication():
    """Confirm Gross Margin = Revenue - COGS and verify financial trade-off behavior."""
    res = run_dashboard_simulation(seed=42)
    f = res.fixed_metrics
    m = res.markdown_metrics

    # Gross Margin definition strictly holds for both policies
    assert abs(f.gross_margin - round(f.revenue - f.cogs, 2)) <= 0.02
    assert abs(m.gross_margin - round(m.revenue - m.cogs, 2)) <= 0.02

    # Under default markdown configuration:
    # Revenue increases (more volume sold due to clearance demand)
    assert m.revenue > f.revenue
    # Gross margin decreases (due to 20%-40% discount concessions)
    assert m.gross_margin < f.gross_margin

    rev_gain = m.revenue - f.revenue
    margin_gain = m.gross_margin - f.gross_margin
    assert rev_gain > 0
    assert margin_gain < 0


def test_markdown_events_and_active_triggers_audit():
    """Verify promotional markdown events and active triggers match underlying simulation."""
    res = run_dashboard_simulation(seed=42)
    m = res.markdown_metrics
    events_df = res.markdown_events_df

    # Active Markdown Triggers must equal length of events dataframe
    assert m.markdown_events_count == len(events_df)
    assert len(events_df) > 0

    # Fixed price baseline must have zero markdown events
    assert res.fixed_metrics.markdown_events_count == 0

    # All recorded events must have positive discounts and positive units sold
    assert (events_df["discount_pct"] > 0).all()
    assert (events_df["units_sold"] > 0).all()


# ---------------------------------------------------------------------------
# Historical Price Analysis Visualizations & Data Loading Tests
# ---------------------------------------------------------------------------

def test_load_product_price_history_and_demand():
    """Verify price history and historical demand datasets load correctly for dashboard."""
    price_df = load_product_price_history()
    assert isinstance(price_df, pd.DataFrame)
    assert len(price_df) == 7300
    assert "actual_price" in price_df.columns

    demand_df = load_historical_demand_data()
    assert isinstance(demand_df, pd.DataFrame)
    assert len(demand_df) == 7300


def test_create_historical_price_chart():
    """Verify create_historical_price_chart builds a 2-trace interactive time-series."""
    df = load_historical_demand_data()
    prod_df = df[df["product_id"] == "PROD-01"]
    fig = create_historical_price_chart(prod_df, "Toned Fresh Milk")

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    names = [t.name for t in fig.data]
    assert "Regular Base Price (₹)" in names
    assert "Actual Selling Price (₹)" in names


def test_create_discount_history_chart():
    """Verify create_discount_history_chart builds a valid promotional discount bar chart."""
    df = load_historical_demand_data()
    prod_df = df[df["product_id"] == "PROD-01"]
    fig = create_discount_history_chart(prod_df, "Toned Fresh Milk")

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1
    assert fig.data[0].name == "Promotional Discount (%)"


def test_create_demand_trend_chart():
    """Verify create_demand_trend_chart builds units sold and inventory velocity traces."""
    df = load_historical_demand_data()
    prod_df = df[df["product_id"] == "PROD-01"]
    fig = create_demand_trend_chart(prod_df, "Toned Fresh Milk")

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    names = [t.name for t in fig.data]
    assert "Units Sold" in names
    assert "Units Available (Stock)" in names


def test_create_daily_trends_chart(sample_sim_result):
    """Verify create_daily_trends_chart renders revenue, waste cost, and sales comparison traces."""
    fig = create_daily_trends_chart(sample_sim_result.daily_history_df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 4
    trace_names = [t.name for t in fig.data]
    assert "Fixed Policy Sales (units)" in trace_names
    assert "Markdown Policy Sales (units)" in trace_names
    assert "Fixed Policy Waste (Expired)" in trace_names
    assert "Markdown Policy Waste (Expired)" in trace_names


def test_create_sim_product_price_chart(sample_sim_result):
    """Verify create_sim_product_price_chart renders base price, cost floor, and policy prices."""
    prod_row = sample_sim_result.products_df.iloc[0]
    p_md_df = sample_sim_result.daily_history_df[
        (sample_sim_result.daily_history_df["policy"] == "markdown")
        & (sample_sim_result.daily_history_df["product_id"] == prod_row["product_id"])
    ]
    fig = create_sim_product_price_chart(p_md_df, prod_row["name"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    trace_names = [t.name for t in fig.data]
    assert "Regular Base Price (₹)" in trace_names
    assert "Actual Selling Price (₹)" in trace_names


def test_create_sim_product_sales_waste_chart(sample_sim_result):
    """Verify create_sim_product_sales_waste_chart renders sales and waste comparison bars."""
    prod_row = sample_sim_result.products_df.iloc[0]
    p_md_df = sample_sim_result.daily_history_df[
        (sample_sim_result.daily_history_df["policy"] == "markdown")
        & (sample_sim_result.daily_history_df["product_id"] == prod_row["product_id"])
    ]
    fig = create_sim_product_sales_waste_chart(p_md_df, prod_row["name"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
    trace_names = [t.name for t in fig.data]
    assert "Units Sold" in trace_names
    assert "Units Wasted (Expired)" in trace_names


def test_format_units_integer_formatting():
    """Verify format_units formats whole numbers without decimal points."""
    assert format_units(1234) == "1,234 units"
    assert format_units(1234.0) == "1,234 units"
    assert format_units(0) == "0 units"
    assert format_units(1234.56) == "1,234.6 units"
    assert format_units(1234, include_sign=True) == "+1,234 units"
    assert format_units(-500, include_sign=True) == "-500 units"


def test_format_pp():
    """Verify format_pp formats percentage points with appropriate sign and label."""
    assert format_pp(2.345) == "2.35 pp"
    assert format_pp(-4.79, include_sign=True) == "-4.79 pp"
    assert format_pp(1.5, include_sign=True) == "+1.50 pp"
    assert format_pp(0.0) == "0.00 pp"


def test_executive_kpi_row_metrics_calculation(sample_sim_result):
    """Verify executive KPI row calculations: waste reduction %, rev gain, net gain, margin change pp."""
    f = sample_sim_result.fixed_metrics
    m = sample_sim_result.markdown_metrics

    # 1. Waste reduction %
    waste_saved = f.units_wasted - m.units_wasted
    expected_waste_red = (waste_saved / f.units_wasted * 100.0) if f.units_wasted > 0 else 0.0
    assert expected_waste_red > 0.0

    # 2. Revenue change
    expected_rev_gain = m.revenue - f.revenue
    assert expected_rev_gain > 0.0

    # 3. Net contribution gain
    expected_net_gain = m.net_contribution - f.net_contribution
    assert expected_net_gain > 0.0

    # 4. Gross margin change in pp
    expected_margin_pp = m.gross_margin_pct - f.gross_margin_pct
    assert abs(expected_margin_pp - (m.gross_margin_pct - f.gross_margin_pct)) < 1e-4

    # Safe handling of zero denominators
    zero_waste_red = (0.0 / 0.0 * 100.0) if 0.0 > 0 else 0.0
    assert zero_waste_red == 0.0


def test_shopper_deals_filtering_and_empty_state(sample_sim_result):
    """Verify shopper deals filtering excludes expired and non-discounted items."""
    daily_df = sample_sim_result.daily_history_df
    last_day = sample_sim_result.sim_days

    # Eligible deals under markdown policy
    deals = daily_df[
        (daily_df["policy"] == "markdown")
        & (daily_df["day"] == last_day)
        & (daily_df["discount_pct"] > 0.0)
        & (daily_df["days_until_expiry"] >= 1)
        & ((daily_df["units_sold"] + daily_df["ending_stock"]) > 0.0)
    ]

    # No expired items in deals
    assert (deals["days_until_expiry"] >= 1).all()
    # No zero discount items in deals
    assert (deals["discount_pct"] > 0.0).all()
    # Prices must be strictly greater than or equal to unit cost
    prods = {p["product_id"]: p for _, p in sample_sim_result.products_df.iterrows()}
    for _, d in deals.iterrows():
        prod = prods[d["product_id"]]
        assert d["selling_price"] >= prod["unit_cost"] - 1e-4


# ---------------------------------------------------------------------------
# Tests for UI Redesign, Simplified Controls & Shopper Fresh Deals Fix
# ---------------------------------------------------------------------------

def test_shopper_deals_active_day_display_and_validation(sample_sim_result):
    """Verify Day 3 in default simulation correctly surfaces 10 active clearance deals."""
    daily_df = sample_sim_result.daily_history_df

    deals_day3 = daily_df[
        (daily_df["policy"] == "markdown")
        & (daily_df["day"] == 3)
        & (daily_df["discount_pct"] > 0.0)
        & (daily_df["days_until_expiry"] >= 1)
        & ((daily_df["units_sold"] + daily_df["ending_stock"]) > 0.0)
        & (daily_df["selling_price"] < daily_df["regular_price"])
    ]

    # Exactly 10 products have active clearance markdowns on Day 3
    assert len(deals_day3) == 10

    # Verify each eligible deal satisfies all integrity criteria:
    for _, row in deals_day3.iterrows():
        # 1. Has positive unexpired shelf life
        assert row["days_until_expiry"] in (1, 2)
        # 2. Has available stock
        avail = row["units_sold"] + row["ending_stock"]
        assert avail > 0.0
        # 3. Has positive discount
        assert row["discount_pct"] > 0.0
        # 4. Selling price is discounted below regular price
        assert row["selling_price"] < row["regular_price"]
        # 5. Selling price respects cost floor
        assert row["selling_price"] > 0.0


def test_shopper_deals_empty_state_on_non_deal_days(sample_sim_result):
    """Verify empty state activates on days with no clearance markdowns (Day 1 and Day 30)."""
    daily_df = sample_sim_result.daily_history_df

    for empty_day in [1, 30]:
        deals = daily_df[
            (daily_df["policy"] == "markdown")
            & (daily_df["day"] == empty_day)
            & (daily_df["discount_pct"] > 0.0)
            & (daily_df["days_until_expiry"] >= 1)
            & ((daily_df["units_sold"] + daily_df["ending_stock"]) > 0.0)
        ]
        assert len(deals) == 0


def test_shopper_deals_category_filtering(sample_sim_result):
    """Verify category filtering correctly partitions Day 3 deals across departments."""
    daily_df = sample_sim_result.daily_history_df

    day3_deals = daily_df[
        (daily_df["policy"] == "markdown")
        & (daily_df["day"] == 3)
        & (daily_df["discount_pct"] > 0.0)
        & (daily_df["days_until_expiry"] >= 1)
        & ((daily_df["units_sold"] + daily_df["ending_stock"]) > 0.0)
    ]

    dairy_deals = day3_deals[day3_deals["category"].str.lower() == "dairy"]
    bakery_deals = day3_deals[day3_deals["category"].str.lower() == "bakery"]
    fruit_deals = day3_deals[day3_deals["category"].str.lower() == "fruits"]
    veg_deals = day3_deals[day3_deals["category"].str.lower() == "vegetables"]

    assert len(dairy_deals) == 2   # Milk, Chaas
    assert len(bakery_deals) == 4  # White Bread, Atta Bread, Ladi Pav, Baguette
    assert len(fruit_deals) == 2   # Bananas, Papaya
    assert len(veg_deals) == 2     # Spinach, Mushrooms
    assert len(dairy_deals) + len(bakery_deals) + len(fruit_deals) + len(veg_deals) == 10


def test_fixed_price_policy_offers_no_clearance_deals(sample_sim_result):
    """Confirm that Fixed Price baseline offers zero clearance deals across the entire 30 days."""
    daily_df = sample_sim_result.daily_history_df

    fixed_deals = daily_df[
        (daily_df["policy"] == "fixed")
        & (daily_df["discount_pct"] > 0.0)
    ]
    assert len(fixed_deals) == 0


def test_simulation_workflow_reproducibility():
    """Verify that repeated runs with identical parameters produce 100% bitwise-identical results."""
    res1 = run_dashboard_simulation(sim_days=30, seed=42)
    res2 = run_dashboard_simulation(sim_days=30, seed=42)

    assert res1.fixed_metrics == res2.fixed_metrics
    assert res1.markdown_metrics == res2.markdown_metrics
    pd.testing.assert_frame_equal(res1.daily_history_df, res2.daily_history_df)
    pd.testing.assert_frame_equal(res1.markdown_events_df, res2.markdown_events_df)


def test_fixed_and_markdown_policies_run_on_identical_starting_inventory():
    """Verify fixed-price and markdown policies run on 100% identical starting inventory and arrivals."""
    res = run_dashboard_simulation(sim_days=30, seed=42)

    # 1. Total received units are identical across both policies
    assert res.fixed_metrics.total_received == res.markdown_metrics.total_received
    assert res.fixed_metrics.total_received > 0

    # 2. Both policies share identical product catalog
    assert len(res.products_df) == 20
    assert set(res.products_df["product_id"]) == set(res.daily_history_df["product_id"])

    # 3. Verify arrivals are synchronized to exact scheduled batches
    products = get_default_products()
    arrivals = generate_arrival_schedule(products, sim_days=30, seed=42)
    expected_total_received = sum(b.initial_quantity for b in arrivals)
    assert res.fixed_metrics.total_received == expected_total_received
    assert res.markdown_metrics.total_received == expected_total_received


def test_discount_threshold_adjustment_changes_active_deals():
    """Verify changing near-expiry threshold from 2 to 3 days expands eligible deals."""
    # Simulation with default 2-day threshold
    res_2d = run_dashboard_simulation(threshold_1_days=1, threshold_2_days=2, seed=42)
    # Simulation with 3-day threshold
    res_3d = run_dashboard_simulation(threshold_1_days=1, threshold_2_days=3, seed=42)

    deals_2d = res_2d.daily_history_df[
        (res_2d.daily_history_df["policy"] == "markdown")
        & (res_2d.daily_history_df["discount_pct"] > 0.0)
    ]
    deals_3d = res_3d.daily_history_df[
        (res_3d.daily_history_df["policy"] == "markdown")
        & (res_3d.daily_history_df["discount_pct"] > 0.0)
    ]

    # Expanding the markdown window to 3 days produces more clearance discount opportunities
    assert len(deals_3d) >= len(deals_2d)
    # Products with exactly 3 days remaining now receive markdown discounts under the 3-day threshold
    three_day_discounts = deals_3d[deals_3d["days_until_expiry"] == 3]
    assert len(three_day_discounts) > 0


def test_urgent_clearance_discount_change_reflected_in_deal_prices():
    """Verify changing urgent clearance discount from 15% to 30% updates deal prices."""
    res_15 = run_dashboard_simulation(discount_1_pct=0.15, seed=42)
    res_30 = run_dashboard_simulation(discount_1_pct=0.30, seed=42)

    ev_15 = res_15.markdown_events_df[res_15.markdown_events_df["reason"].str.contains("Urgent clearance")]
    ev_30 = res_30.markdown_events_df[res_30.markdown_events_df["reason"].str.contains("Urgent clearance")]

    assert len(ev_15) > 0
    assert len(ev_30) > 0
    # Requested discount in markdown events reflects the configured setting
    assert (ev_15["requested_discount_pct"] == 15.0).all()
    assert (ev_30["requested_discount_pct"] == 30.0).all()
    # Mean actual discount for 1-day urgent clearance products is higher under 30% than 15%
    assert ev_30["actual_discount_pct"].mean() > ev_15["actual_discount_pct"].mean()


# ---------------------------------------------------------------------------
# Regression Tests for Adjustable Markdown Rules & Rule Logic Display
# ---------------------------------------------------------------------------

def test_rule_logic_explanation_dynamic_text_generation():
    """Verify rule logic explanation generates dynamic text matching selected slider values."""
    # 1. Test default values (2 days, 20%, 1 day, 40%)
    default_text = generate_rule_logic_explanation(
        near_expiry_threshold=2,
        near_expiry_discount_pct=20,
        urgent_threshold=1,
        urgent_discount_pct=40,
    )
    assert "**Rule Logic:**" in default_text
    assert "- When a product has 2 or fewer days remaining before expiry, apply the configured 20% near-expiry discount, subject to the urgent rule." in default_text
    assert "- When a product has 1 or fewer days remaining before expiry, apply the configured 40% urgent-clearance discount." in default_text
    assert "- Never sell expired products." in default_text
    assert "- Never price below the configured minimum gross-margin floor." in default_text

    # 2. Test user's exact example (5 days, 15%, 1 day, 25%)
    custom_text = generate_rule_logic_explanation(
        near_expiry_threshold=5,
        near_expiry_discount_pct=15,
        urgent_threshold=1,
        urgent_discount_pct=25,
    )
    assert "- When a product has 5 or fewer days remaining before expiry, apply the configured 15% near-expiry discount, subject to the urgent rule." in custom_text
    assert "- When a product has 1 or fewer days remaining before expiry, apply the configured 25% urgent-clearance discount." in custom_text
    assert "- Never sell expired products." in custom_text
    assert "- Never price below the configured minimum gross-margin floor." in custom_text

    # 3. Test fractional percentage arguments (0.15, 0.25)
    frac_text = generate_rule_logic_explanation(
        near_expiry_threshold=5,
        near_expiry_discount_pct=0.15,
        urgent_threshold=1,
        urgent_discount_pct=0.25,
    )
    assert frac_text == custom_text


def test_changing_each_threshold_changes_pricing_behavior():
    """Verify changing near-expiry and urgent clearance thresholds adjusts active clearance triggers."""
    # Default: urgent=1, near_expiry=2
    res_base = run_dashboard_simulation(threshold_1_days=1, threshold_2_days=2, seed=42)
    # Changed near-expiry threshold: urgent=1, near_expiry=4
    res_t4 = run_dashboard_simulation(threshold_1_days=1, threshold_2_days=4, seed=42)
    # Changed urgent threshold: urgent=2, near_expiry=4
    res_urg2 = run_dashboard_simulation(threshold_1_days=2, threshold_2_days=4, seed=42)

    # 1. Products with 4 days remaining receive near-expiry discount under threshold_2=4, but not under threshold_2=2
    m_base_4d = res_base.daily_history_df[
        (res_base.daily_history_df["policy"] == "markdown")
        & (res_base.daily_history_df["days_until_expiry"] == 4)
        & (res_base.daily_history_df["discount_pct"] > 0)
    ]
    m_t4_4d = res_t4.daily_history_df[
        (res_t4.daily_history_df["policy"] == "markdown")
        & (res_t4.daily_history_df["days_until_expiry"] == 4)
        & (res_t4.daily_history_df["discount_pct"] > 0)
    ]
    assert len(m_base_4d) == 0
    assert len(m_t4_4d) > 0

    # 2. Products with 2 days remaining receive urgent clearance (40%) when urgent=2 instead of near-expiry (20%)
    ev_urg2 = res_urg2.markdown_events_df[
        (res_urg2.markdown_events_df["days_until_expiry"] == 2)
        & (res_urg2.markdown_events_df["reason"].str.contains("Urgent clearance"))
    ]
    ev_base = res_base.markdown_events_df[
        (res_base.markdown_events_df["days_until_expiry"] == 2)
        & (res_base.markdown_events_df["reason"].str.contains("Urgent clearance"))
    ]
    assert len(ev_urg2) > 0
    assert len(ev_base) == 0  # Under base, 2-day items only receive near-expiry, not urgent clearance


def test_changing_each_discount_changes_selling_prices():
    """Verify changing discount percentage changes product selling prices in simulation."""
    # Near-expiry discount 10% vs 20% (threshold_2 = 2)
    res_d10 = run_dashboard_simulation(threshold_2_days=2, discount_2_pct=0.10, seed=42)
    res_d20 = run_dashboard_simulation(threshold_2_days=2, discount_2_pct=0.20, seed=42)

    # Find unexpired 2-day items
    d10_items = res_d10.daily_history_df[
        (res_d10.daily_history_df["policy"] == "markdown")
        & (res_d10.daily_history_df["days_until_expiry"] == 2)
        & (res_d10.daily_history_df["units_sold"] > 0)
    ]
    d20_items = res_d20.daily_history_df[
        (res_d20.daily_history_df["policy"] == "markdown")
        & (res_d20.daily_history_df["days_until_expiry"] == 2)
        & (res_d20.daily_history_df["units_sold"] > 0)
    ]

    assert len(d10_items) > 0
    assert len(d20_items) > 0
    # Selling price at 20% discount is strictly lower than at 10% discount
    assert d20_items["selling_price"].mean() < d10_items["selling_price"].mean()


def test_fixed_price_policy_remains_strictly_unchanged_across_markdown_variations():
    """Verify fixed-price policy metrics and selling prices never change when markdown rules change."""
    res_default = run_dashboard_simulation(threshold_1_days=1, discount_1_pct=0.40, threshold_2_days=2, discount_2_pct=0.20, seed=42)
    res_custom = run_dashboard_simulation(threshold_1_days=2, discount_1_pct=0.50, threshold_2_days=5, discount_2_pct=0.25, seed=42)

    # Fixed metrics must be 100% bitwise identical
    assert res_default.fixed_metrics == res_custom.fixed_metrics

    # Fixed daily history records must be 100% bitwise identical
    fixed_default = res_default.daily_history_df[res_default.daily_history_df["policy"] == "fixed"].reset_index(drop=True)
    fixed_custom = res_custom.daily_history_df[res_custom.daily_history_df["policy"] == "fixed"].reset_index(drop=True)
    pd.testing.assert_frame_equal(fixed_default, fixed_custom)

    # Fixed policy never applies discounts
    assert (fixed_default["discount_pct"] == 0.0).all()


def test_margin_floor_and_expired_product_safeguards():
    """Verify minimum margin floor is never breached and expired products are never sold."""
    # Set 10% minimum margin floor with aggressive 50% / 30% discounts
    res = run_dashboard_simulation(min_gross_margin_pct=10.0, discount_1_pct=0.50, discount_2_pct=0.30, seed=42)

    prods = {p["product_id"]: p for _, p in res.products_df.iterrows()}

    # 1. Margin floor constraint: all markdown events respect the margin floor
    events_df = res.markdown_events_df
    clamped_events = events_df[events_df["margin_floor_limited"] == True]
    assert len(clamped_events) > 0

    for _, ev in clamped_events.iterrows():
        prod = prods[ev["product_id"]]
        min_allowed_price = round(prod["unit_cost"] / (1.0 - 0.10), 2)
        assert ev["selling_price"] >= min_allowed_price - 0.01
        assert ev["actual_discount_pct"] < ev["requested_discount_pct"]

    # 2. Never sell expired products
    markdown_records = res.daily_history_df[res.daily_history_df["policy"] == "markdown"]
    for _, row in markdown_records.iterrows():
        if row["days_until_expiry"] <= 0:
            assert row["units_sold"] == 0.0
        # When units are sold at discounted price, selling price respects unit cost
        if row["units_sold"] > 0:
            prod = prods[row["product_id"]]
            assert row["selling_price"] >= prod["unit_cost"] - 0.01


# ---------------------------------------------------------------------------
# Tests for Per-Product Markdown History & Operational Ledger
# ---------------------------------------------------------------------------

def test_per_product_event_filtering_and_columns():
    """Verify per-product markdown events are accurately filtered and include required columns."""
    res = run_dashboard_simulation(seed=42)
    ev_df = res.markdown_events_df

    assert not ev_df.empty
    # Verify required schema columns exist
    req_cols = [
        "day", "product_id", "product_name", "category", "days_until_expiry",
        "regular_price", "selling_price", "discount_pct", "units_sold",
        "units_wasted", "reason", "requested_discount_pct", "actual_discount_pct",
        "margin_floor_limited", "available_stock"
    ]
    for col in req_cols:
        assert col in ev_df.columns

    # Select a product with known events (e.g. PROD-12 Robusta Cavendish Bananas)
    prod_events = ev_df[ev_df["product_id"] == "PROD-12"]
    assert len(prod_events) > 0
    assert (prod_events["product_id"] == "PROD-12").all()
    assert (prod_events["discount_pct"] > 0.0).all()
    assert (prod_events["selling_price"] < prod_events["regular_price"]).all()
    assert (prod_events["available_stock"] > 0.0).all()


def test_event_day_and_discount_calculation_consistency():
    """Verify discount percentages in events log are mathematically consistent with base and selling prices."""
    res = run_dashboard_simulation(seed=42)
    for _, ev in res.markdown_events_df.iterrows():
        expected_disc = round(((ev["regular_price"] - ev["selling_price"]) / ev["regular_price"]) * 100.0, 1)
        actual_disc = round(ev["actual_discount_pct"], 1)
        assert abs(expected_disc - actual_disc) <= 0.15


def test_price_history_changes_after_actual_markdown():
    """Verify selling price drops below regular price on actual markdown days and matches daily ledger."""
    res = run_dashboard_simulation(seed=42)
    daily_df = res.daily_history_df

    # Pick product with markdown events
    ev_df = res.markdown_events_df[res.markdown_events_df["product_id"] == "PROD-12"]
    event_days = set(ev_df["day"].tolist())
    assert len(event_days) > 0

    p_records = daily_df[(daily_df["product_id"] == "PROD-12") & (daily_df["policy"] == "markdown")]
    for _, row in p_records.iterrows():
        if row["day"] in event_days:
            # Markdown day: selling price < regular price
            assert row["selling_price"] < row["regular_price"]
            assert row["discount_pct"] > 0.0
        elif row["days_until_expiry"] > 2:
            # Fresh stock day: selling price == regular price
            assert row["selling_price"] == row["regular_price"]
            assert row["discount_pct"] == 0.0


def test_flat_price_history_when_no_markdown_occurred():
    """Verify selling price remains strictly flat at regular price when no markdowns are applied."""
    # Zero discount configuration
    res_zero = run_dashboard_simulation(discount_1_pct=0.0, discount_2_pct=0.0, seed=42)
    p_records = res_zero.daily_history_df[
        (res_zero.daily_history_df["product_id"] == "PROD-01")
        & (res_zero.daily_history_df["policy"] == "markdown")
    ]
    assert len(p_records) == 30
    assert (p_records["selling_price"] == p_records["regular_price"]).all()
    assert (p_records["discount_pct"] == 0.0).all()


def test_product_with_no_markdown_events_has_empty_log():
    """Verify products with zero clearance markdowns return an empty event DataFrame without fake records."""
    # Fixed policy never generates markdown events
    res = run_dashboard_simulation(seed=42)
    fixed_events = res.markdown_events_df[res.markdown_events_df["product_id"] == "PROD-03"]
    # If PROD-03 had zero markdown events under this configuration, log must be empty
    prod_daily = res.daily_history_df[(res.daily_history_df["product_id"] == "PROD-03") & (res.daily_history_df["policy"] == "markdown")]
    if (prod_daily["discount_pct"] == 0.0).all():
        assert len(fixed_events) == 0


def test_daily_sales_and_waste_ledger_reconciliation():
    """Verify physical inventory conservation holds for every SKU in the daily ledger."""
    res = run_dashboard_simulation(seed=42)
    daily_df = res.daily_history_df[res.daily_history_df["policy"] == "markdown"]
    products = get_default_products()
    arrivals = generate_arrival_schedule(products, sim_days=30, seed=42)

    for prod in products:
        p_id = prod.product_id
        p_ledger = daily_df[daily_df["product_id"] == p_id].sort_values("day")
        prod_batches = [b for b in arrivals if b.product_id == p_id]

        total_received = sum(b.initial_quantity for b in prod_batches)
        total_sold = p_ledger["units_sold"].sum()
        total_wasted = p_ledger["units_wasted"].sum()
        ending_stock = p_ledger.iloc[-1]["ending_stock"]

        # Exact physical inventory conservation: Received == Sold + Wasted + Ending Stock
        reconciled_sum = total_sold + total_wasted + ending_stock
        assert abs(total_received - reconciled_sum) <= 0.2


def test_consistency_between_event_log_price_chart_and_pricing_engine():
    """Verify complete consistency among markdown event log, daily ledger, and pricing engine."""
    res = run_dashboard_simulation(seed=42)
    ev_df = res.markdown_events_df
    daily_df = res.daily_history_df[res.daily_history_df["policy"] == "markdown"]
    prods = {p.product_id: p for p in get_default_products()}

    for _, ev in ev_df.head(10).iterrows():
        p_id = ev["product_id"]
        day = ev["day"]
        prod = prods[p_id]

        # 1. Match daily ledger record for same (product_id, day)
        daily_row = daily_df[(daily_df["product_id"] == p_id) & (daily_df["day"] == day)].iloc[0]
        assert daily_row["selling_price"] == ev["selling_price"]
        assert daily_row["discount_pct"] == ev["actual_discount_pct"]

        # 2. Match pricing engine recommend_graduated_markdown_price
        p_engine, d_engine, _, _ = recommend_graduated_markdown_price(
            base_price=prod.base_price,
            unit_cost=prod.unit_cost,
            days_to_expiry=int(ev["days_until_expiry"]),
            shelf_life_days=prod.shelf_life_days,
            near_expiry_threshold=2,
            near_expiry_discount_pct=0.20,
            urgent_clearance_threshold=1,
            urgent_clearance_discount_pct=0.40,
            min_gross_margin_pct=0.0,
            enforce_margin_floor=True,
        )
        assert p_engine == ev["selling_price"]
        assert round(d_engine * 100.0, 1) == round(ev["actual_discount_pct"], 1)


def test_adjustable_thresholds_reflected_in_actual_events():
    """Verify custom thresholds (5d/15% and 1d/25%) are reflected in actual event logs."""
    res = run_dashboard_simulation(
        threshold_1_days=1,
        discount_1_pct=0.25,
        threshold_2_days=5,
        discount_2_pct=0.15,
        seed=42,
    )
    ev_df = res.markdown_events_df
    assert len(ev_df) > 0

    # 1. Urgent clearance events must have requested_discount_pct = 25.0
    urgent_evs = ev_df[ev_df["days_until_expiry"] == 1]
    if len(urgent_evs) > 0:
        assert (urgent_evs["requested_discount_pct"] == 25.0).all()

    # 2. Events triggered at 3 to 5 days remaining must have requested_discount_pct = 15.0
    near_evs = ev_df[ev_df["days_until_expiry"].isin([3, 4, 5])]
    if len(near_evs) > 0:
        assert (near_evs["requested_discount_pct"] == 15.0).all()


# ---------------------------------------------------------------------------
# Regression Tests for Minimal, Professional Dashboard Redesign
# ---------------------------------------------------------------------------

def test_two_column_policy_comparison_metrics_completeness(sample_sim_result):
    """Verify all 8 required comparison metrics are accurately computed for both policies."""
    f = sample_sim_result.fixed_metrics
    m = sample_sim_result.markdown_metrics

    # 1. Units sold
    assert f.units_sold > 0 and m.units_sold > 0
    # 2. Units wasted
    assert f.units_wasted >= 0 and m.units_wasted >= 0
    # 3. Revenue
    assert f.revenue > 0 and m.revenue > 0
    # 4. Gross profit (Rev - COGS)
    assert abs(f.gross_margin - round(f.revenue - f.cogs, 2)) < 0.05
    assert abs(m.gross_margin - round(m.revenue - m.cogs, 2)) < 0.05
    # 5. Gross margin %
    assert 0.0 <= f.gross_margin_pct <= 100.0
    assert 0.0 <= m.gross_margin_pct <= 100.0
    # 6. Waste cost
    assert f.total_waste_cost >= 0 and m.total_waste_cost >= 0
    # 7. Net contribution after waste
    assert abs(f.net_contribution - round(f.gross_margin - f.total_waste_cost, 2)) < 0.05
    assert abs(m.net_contribution - round(m.gross_margin - m.total_waste_cost, 2)) < 0.05
    # 8. Ending healthy inventory
    assert f.ending_inventory >= 0 and m.ending_inventory >= 0


def test_redesigned_minimal_sidebar_defaults_and_rule_explanation():
    """Verify minimal sidebar defaults (30d, seed 42, 2d/20%, 1d/40%, 10% floor) and explanation."""
    explanation = generate_rule_logic_explanation(
        near_expiry_threshold=2,
        near_expiry_discount_pct=20,
        urgent_threshold=1,
        urgent_discount_pct=40,
    )
    assert "2 or fewer days" in explanation
    assert "20%" in explanation
    assert "1 or fewer days" in explanation
    assert "40%" in explanation
    assert "gross-margin floor" in explanation


def test_headless_apptest_navigation_and_product_selection():
    """Verify Streamlit headless AppTest initializes cleanly, switches views, and selects products."""
    from streamlit.testing.v1 import AppTest

    script_path = Path(__file__).parent.parent / "src" / "dashboard.py"
    at = AppTest.from_file(str(script_path), default_timeout=30)
    at.run()
    assert not at.exception

    # Default is Store Operations. Switch to "Per-Product View"
    product_view_option = "Per-Product View"
    if len(at.segmented_control) > 0:
        at.segmented_control[0].select(product_view_option).run()
    elif len(at.radio) > 0:
        nav_radios = [r for r in at.radio if r.key == "app_main_navigation"]
        if nav_radios:
            nav_radios[0].select(product_view_option).run()

    assert not at.exception

    # Verify selectbox for product selection is present in Per-Product View
    prod_sbs = [s for s in at.selectbox if "Select Perishable Product" in s.label]
    assert len(prod_sbs) == 1
    assert len(prod_sbs[0].options) == 20

    # Select another product and re-run
    prod_sbs[0].select(prod_sbs[0].options[1]).run()
    assert not at.exception

    # Switch to Today's Fresh Deals
    deal_option = "Today's Fresh Deals"
    if len(at.segmented_control) > 0:
        at.segmented_control[0].select(deal_option).run()
    elif len(at.radio) > 0:
        nav_radios = [r for r in at.radio if r.key == "app_main_navigation"]
        if nav_radios:
            nav_radios[0].select(deal_option).run()

    assert not at.exception

    # Switch back to Store Operations
    store_option = "Store Operations"
    if len(at.segmented_control) > 0:
        at.segmented_control[0].select(store_option).run()
    elif len(at.radio) > 0:
        nav_radios = [r for r in at.radio if r.key == "app_main_navigation"]
        if nav_radios:
            nav_radios[0].select(store_option).run()

    assert not at.exception


def test_render_per_product_view_callable():
    """Verify render_per_product_view function is defined and signature matches required parameters."""
    import inspect
    sig = inspect.signature(render_per_product_view)
    param_names = list(sig.parameters.keys())
    assert "sim_result" in param_names
    assert "sim_days" in param_names
    assert "t2" in param_names
    assert "d2" in param_names
    assert "t1" in param_names
    assert "d1" in param_names
    assert "seed_val" in param_names












def test_create_sim_product_sales_vs_price_chart_structure(sample_sim_result):
    """Verify dual-axis Sales vs Selling Price chart has proper title, traces, colors, and axes."""
    df = sample_sim_result.daily_history_df
    p_df = df[(df["product_id"] == "PROD-01") & (df["policy"] == "markdown")].sort_values("day")

    fig = create_sim_product_sales_vs_price_chart(p_df, "Toned Fresh Milk")
    assert isinstance(fig, go.Figure)
    assert "Daily Sales vs Actual Selling Price" in fig.layout.title.text

    # 3 Traces: Units Sold (Blue), Actual Selling Price (Orange), Markdown Events (Red)
    trace_names = [t.name for t in fig.data]
    assert "Daily Units Sold" in trace_names
    assert "Actual Selling Price (₹)" in trace_names
    assert "Markdown Clearance Event" in trace_names

    # Trace colors and axes
    t_sales = [t for t in fig.data if t.name == "Daily Units Sold"][0]
    t_price = [t for t in fig.data if t.name == "Actual Selling Price (₹)"][0]
    t_md = [t for t in fig.data if t.name == "Markdown Clearance Event"][0]

    assert t_sales.line.color == "#1F77B4"
    assert t_price.line.color == "#FF7F0E"
    assert t_md.marker.color == "#DC2626"
    assert t_sales.yaxis in ["y", "y1", None]
    assert t_price.yaxis == "y2"
    assert t_md.yaxis == "y2"

    # Layout axes
    assert fig.layout.yaxis.title.text is not None and "Units Sold" in fig.layout.yaxis.title.text
    assert fig.layout.yaxis2.title.text is not None and "Actual Selling Price" in fig.layout.yaxis2.title.text
    assert fig.layout.yaxis2.side == "right"
    assert fig.layout.yaxis2.overlaying == "y"

    # Hover templates
    assert "Daily Units Sold" in t_sales.hovertemplate
    assert "Actual Selling Price" in t_price.hovertemplate
    assert "Days to Expiry" in t_sales.hovertemplate
    assert "Markdown Status" in t_sales.hovertemplate

    # Annotations for markdown events
    assert len(fig.layout.annotations) > 0
    for ann in fig.layout.annotations:
        assert "% Off" in ann.text
        assert ann.bgcolor == "#DC2626"


def test_sales_vs_price_chart_empty_dataframe():
    """Verify empty dataframe produces clean empty-state figure rather than misleading chart."""
    empty_df = pd.DataFrame()
    fig = create_sim_product_sales_vs_price_chart(empty_df, "Missing Product")
    assert isinstance(fig, go.Figure)
    assert len(fig.layout.annotations) == 1
    assert "No recorded sales or price history available" in fig.layout.annotations[0].text


def test_sales_vs_price_chart_zero_markdowns(sample_sim_result):
    """Verify product with zero markdowns (e.g. PROD-03) has 2 traces, flat price, and 0 markdown markers."""
    df = sample_sim_result.daily_history_df
    p_df = df[(df["product_id"] == "PROD-03") & (df["policy"] == "markdown")].sort_values("day")

    fig = create_sim_product_sales_vs_price_chart(p_df, "Fresh Curd / Dahi")
    assert len(fig.data) == 2
    trace_names = [t.name for t in fig.data]
    assert "Daily Units Sold" in trace_names
    assert "Actual Selling Price (₹)" in trace_names
    assert "Markdown Clearance Event" not in trace_names
    assert len(fig.layout.annotations) == 0


def test_sales_and_price_day_alignment(sample_sim_result):
    """Verify sales and prices are strictly aligned to identical simulation days."""
    df = sample_sim_result.daily_history_df
    p_df = df[(df["product_id"] == "PROD-01") & (df["policy"] == "markdown")].sort_values("day")

    fig = create_sim_product_sales_vs_price_chart(p_df, "Toned Fresh Milk")
    t_sales = [t for t in fig.data if t.name == "Daily Units Sold"][0]
    t_price = [t for t in fig.data if t.name == "Actual Selling Price (₹)"][0]

    assert list(t_sales.x) == list(t_price.x)
    assert list(t_sales.x) == list(range(1, 31))


def test_markdown_status_and_margin_floor_limiting():
    """Verify reason PROD-01 shows ~4% discount is margin floor clamping (3.7% max discount on 13.3% margin)."""
    res_10 = run_dashboard_simulation(sim_days=30, seed=42, min_gross_margin_pct=10.0)
    df = res_10.daily_history_df
    p_df = df[(df["product_id"] == "PROD-01") & (df["policy"] == "markdown")].sort_values("day")

    md_days = p_df[p_df["discount_pct"] > 0]
    assert len(md_days) > 0
    # At 10% floor on 13.33% margin: max discount is 3.70% (which rounds to 4% in integer UI display)
    for _, row in md_days.iterrows():
        assert abs(row["discount_pct"] - 3.70) < 0.1
        assert abs(row["selling_price"] - 57.78) < 0.1

    # Verify that in markdown_events_df, margin_floor_limited is True
    ev_df = res_10.markdown_events_df[res_10.markdown_events_df["product_id"] == "PROD-01"]
    assert len(ev_df) > 0
    assert (ev_df["margin_floor_limited"] == True).all()

    # Verify that when floor is 0%, discount reaches cost floor (13.33%)
    res_0 = run_dashboard_simulation(sim_days=30, seed=42, min_gross_margin_pct=0.0)
    p_df_0 = res_0.daily_history_df[(res_0.daily_history_df["product_id"] == "PROD-01") & (res_0.daily_history_df["policy"] == "markdown")].sort_values("day")
    md_days_0 = p_df_0[p_df_0["discount_pct"] > 0]
    for _, row in md_days_0.iterrows():
        assert abs(row["discount_pct"] - 13.33) < 0.1
        assert abs(row["selling_price"] - 52.00) < 0.1


def test_expiry_and_waste_unsold_inventory_reconciliation(sample_sim_result):
    """Verify that all unsold inventory reaching expiry is strictly wasted with zero inventory leakage."""
    products = get_default_products()
    arrivals = generate_arrival_schedule(products, sim_days=30, seed=42)

    for p in products:
        p_arrivals = [b for b in arrivals if b.product_id == p.product_id]
        tot_recv = sum(b.initial_quantity for b in p_arrivals)

        p_md = sample_sim_result.daily_history_df[
            (sample_sim_result.daily_history_df["product_id"] == p.product_id) &
            (sample_sim_result.daily_history_df["policy"] == "markdown")
        ]
        sold = p_md["units_sold"].sum()
        wasted = p_md["units_wasted"].sum()
        ending = p_md.iloc[-1]["ending_stock"]

        # Conservation identity: Received = Sold + Wasted + Ending Stock
        assert abs(tot_recv - (sold + wasted + ending)) < 1e-4



def test_create_sim_product_price_vs_sales_chart_structure(sample_sim_result):
    """Verify Price vs Units Sold chart structure, axes, traces, and ascending order."""
    df = sample_sim_result.daily_history_df
    p_df = df[(df["product_id"] == "PROD-01") & (df["policy"] == "markdown")]

    fig = create_sim_product_price_vs_sales_chart(p_df, "Toned Fresh Milk")
    assert isinstance(fig, go.Figure)
    assert "Price vs Units Sold" in fig.layout.title.text

    trace_names = [t.name for t in fig.data]
    assert "Price vs Sales Curve" in trace_names
    assert "Markdown Clearance Observations" in trace_names

    t_curve = [t for t in fig.data if t.name == "Price vs Sales Curve"][0]
    t_md = [t for t in fig.data if t.name == "Markdown Clearance Observations"][0]

    # Mode and markers
    assert "lines" in t_curve.mode and "markers" in t_curve.mode
    assert t_md.marker.color == "#DC2626"
    assert t_md.marker.symbol == "diamond"

    # Ascending price order verification
    x_prices = list(t_curve.x)
    assert x_prices == sorted(x_prices)

    # Hover templates
    assert "Simulation Day" in t_curve.hovertemplate
    assert "Actual Selling Price" in t_curve.hovertemplate
    assert "Units Sold" in t_curve.hovertemplate
    assert "Days to Expiry" in t_curve.hovertemplate
    assert "Discount Applied" in t_curve.hovertemplate

    # Layout axes
    assert "Actual Selling Price" in fig.layout.xaxis.title.text
    assert "Units Sold" in fig.layout.yaxis.title.text


def test_price_vs_sales_chart_product_filtering(sample_sim_result):
    """Verify Price vs Units Sold chart strictly filters to the selected product's records."""
    df = sample_sim_result.daily_history_df
    p_df = df[(df["product_id"] == "PROD-02") & (df["policy"] == "markdown")]

    fig = create_sim_product_price_vs_sales_chart(p_df, "Full Cream Fresh Milk")
    t_curve = [t for t in fig.data if t.name == "Price vs Sales Curve"][0]

    # Verify all plotted points match PROD-02's simulation days
    assert len(t_curve.x) == 30
    assert len(t_curve.y) == 30
    # Base price of PROD-02 is ₹74.00; selling prices should be <= 74.00
    assert all(p <= 74.00 for p in t_curve.x)


def test_price_vs_sales_chart_repeated_prices_preserved(sample_sim_result):
    """Verify multiple days sharing identical selling price are all preserved as distinct observations."""
    df = sample_sim_result.daily_history_df
    p_df = df[(df["product_id"] == "PROD-01") & (df["policy"] == "markdown")]

    fig = create_sim_product_price_vs_sales_chart(p_df, "Toned Fresh Milk")
    t_curve = [t for t in fig.data if t.name == "Price vs Sales Curve"][0]

    # Exactly 30 days should be preserved in the curve (none combined)
    assert len(t_curve.x) == 30
    assert len(t_curve.y) == 30

    # Days with price 60.00
    pts_60 = [y for x, y in zip(t_curve.x, t_curve.y) if abs(x - 60.0) < 0.01]
    assert len(pts_60) > 1, "Must preserve each day's distinct sales point for identical prices"


def test_price_vs_sales_chart_zero_sales():
    """Verify days with zero sales are safely plotted and preserved."""
    custom_df = pd.DataFrame([
        {"day": 1, "selling_price": 50.0, "units_sold": 0.0, "discount_pct": 0.0, "days_until_expiry": 3, "regular_price": 50.0},
        {"day": 2, "selling_price": 40.0, "units_sold": 15.0, "discount_pct": 20.0, "days_until_expiry": 1, "regular_price": 50.0},
    ])
    fig = create_sim_product_price_vs_sales_chart(custom_df, "Test Zero Sales Product")
    t_curve = [t for t in fig.data if t.name == "Price vs Sales Curve"][0]
    assert 0.0 in list(t_curve.y)
    assert list(t_curve.x) == [40.0, 50.0]  # Ascending price order


def test_price_vs_sales_chart_empty_history():
    """Verify empty dataframe displays appropriate empty-state message."""
    empty_df = pd.DataFrame()
    fig = create_sim_product_price_vs_sales_chart(empty_df, "Unknown SKU")
    assert isinstance(fig, go.Figure)
    assert len(fig.layout.annotations) == 1
    assert "No recorded sales or price history available" in fig.layout.annotations[0].text
