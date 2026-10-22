"""Unit tests for FreshPrice AI Streamlit Dashboard Module (NEXAI 2026 Hackathon PS 4.1)."""

from pathlib import Path
import pytest
import plotly.graph_objects as go
import pandas as pd

from src.dashboard import (
    create_comparison_chart,
    create_waste_comparison_chart,
    format_inr,
    format_pct,
    format_units,
    run_dashboard_simulation,
)
from src.store_simulator import (
    MarkdownPolicyConfig,
    run_store_simulation,
)


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

