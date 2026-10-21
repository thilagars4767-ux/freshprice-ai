"""Unit tests for FreshPrice AI Performance Evaluation and Sensitivity Analysis (Phase 3)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.performance_analysis import (
    evaluate_category_performance,
    evaluate_discount_sensitivity,
    evaluate_elasticity_sensitivity,
    generate_charts,
    generate_markdown_report,
    run_phase3_analysis,
    safe_pct_change,
)
from src.pricing_engine import DEFAULT_INVENTORY_FILE, PricingPolicyConfig, load_inventory


@pytest.fixture
def sample_inventory():
    """Load default 120-record synthetic grocery dataset."""
    return load_inventory(DEFAULT_INVENTORY_FILE)


def test_category_performance_all_five_categories_represented(sample_inventory):
    """Verify all 5 grocery categories are represented in category evaluation."""
    cat_df = evaluate_category_performance(sample_inventory)
    expected_categories = {"bakery", "dairy", "fruits", "packaged food", "vegetables"}
    assert set(cat_df["category"].str.lower()) == expected_categories
    assert len(cat_df) == 5
    assert (cat_df["batch_count"] == 24).all()
    assert (cat_df["initial_stock"] > 0).all()


def test_discount_sensitivity_all_requested_settings(sample_inventory):
    """Verify sensitivity settings include 10%, 20%, 30%, and 35%."""
    disc_df = evaluate_discount_sensitivity(sample_inventory, discount_caps=[0.10, 0.20, 0.30, 0.35])
    expected_caps = {0.0, 0.10, 0.20, 0.30, 0.35}
    assert set(disc_df["max_discount_float"]) == expected_caps
    assert len(disc_df) == 5

    # As discount cap relaxes, units sold should be monotonically non-decreasing
    assert (disc_df["units_sold"].diff().dropna() >= -1e-6).all()


def test_elasticity_sensitivity_all_requested_settings(sample_inventory):
    """Verify elasticity settings include 0.5, 1.0, 1.5, and 2.0."""
    elas_df = evaluate_elasticity_sensitivity(sample_inventory, elasticity_magnitudes=[0.5, 1.0, 1.5, 2.0])
    expected_mags = {0.5, 1.0, 1.5, 2.0}
    assert set(elas_df["elasticity_magnitude"]) == expected_mags
    assert len(elas_df) == 4

    # At inelastic settings (0.5 and 1.0), profitability protections hold regular prices
    assert elas_df.loc[elas_df["elasticity_magnitude"] == 0.5, "waste_reduction_vs_fixed_pct"].values[0] == 0.0
    assert elas_df.loc[elas_df["elasticity_magnitude"] == 1.0, "waste_reduction_vs_fixed_pct"].values[0] == 0.0

    # At elastic settings (1.5 and 2.0), waste reduction is strictly positive and increases
    w_15 = elas_df.loc[elas_df["elasticity_magnitude"] == 1.5, "waste_reduction_vs_fixed_pct"].values[0]
    w_20 = elas_df.loc[elas_df["elasticity_magnitude"] == 2.0, "waste_reduction_vs_fixed_pct"].values[0]
    assert w_15 > 50.0
    assert w_20 > w_15


def test_output_summaries_required_columns(sample_inventory):
    """Verify output summaries contain all required columns."""
    cat_df = evaluate_category_performance(sample_inventory)
    required_cat_cols = [
        "category",
        "batch_count",
        "initial_stock",
        "fixed_units_sold",
        "dynamic_units_sold",
        "fixed_unsold_units",
        "dynamic_unsold_units",
        "fixed_waste_rate_pct",
        "dynamic_waste_rate_pct",
        "waste_reduction_pct",
        "fixed_revenue",
        "dynamic_revenue",
        "fixed_gross_profit",
        "dynamic_gross_profit",
        "fixed_waste_loss",
        "dynamic_waste_loss",
        "fixed_net_profit",
        "dynamic_net_profit",
        "net_profit_diff",
    ]
    for col in required_cat_cols:
        assert col in cat_df.columns

    disc_df = evaluate_discount_sensitivity(sample_inventory)
    required_disc_cols = [
        "max_discount_setting",
        "max_discount_float",
        "units_sold",
        "unsold_units",
        "waste_rate_pct",
        "waste_reduction_vs_fixed_pct",
        "revenue",
        "cogs",
        "gross_profit",
        "waste_loss",
        "net_profit",
        "profit_diff_vs_fixed",
    ]
    for col in required_disc_cols:
        assert col in disc_df.columns

    elas_df = evaluate_elasticity_sensitivity(sample_inventory)
    required_elas_cols = [
        "elasticity_scenario",
        "elasticity_magnitude",
        "units_sold",
        "unsold_units",
        "waste_rate_pct",
        "waste_reduction_vs_fixed_pct",
        "revenue",
        "cogs",
        "gross_profit",
        "waste_loss",
        "net_profit",
        "profit_diff_vs_fixed",
    ]
    for col in required_elas_cols:
        assert col in elas_df.columns


def test_safe_pct_change_handles_zero_baselines():
    """Verify percentage change calculation safely handles zero and negative baselines."""
    # Zero baseline returns 0.0 without ZeroDivisionError
    assert safe_pct_change(10.0, 0.0) == 0.0
    assert safe_pct_change(0.0, 0.0) == 0.0

    # Normal calculations
    assert safe_pct_change(150.0, 100.0) == 50.0
    assert safe_pct_change(50.0, 100.0) == -50.0


def test_waste_rate_calculations(sample_inventory):
    """Verify waste rate and percentage waste reduction formulas."""
    cat_df = evaluate_category_performance(sample_inventory)

    for _, row in cat_df.iterrows():
        # Waste rate check
        expected_f_rate = round((row["fixed_unsold_units"] / row["initial_stock"]) * 100.0, 2)
        assert abs(row["fixed_waste_rate_pct"] - expected_f_rate) <= 0.02

        expected_d_rate = round((row["dynamic_unsold_units"] / row["initial_stock"]) * 100.0, 2)
        assert abs(row["dynamic_waste_rate_pct"] - expected_d_rate) <= 0.02

        # Waste reduction check
        if row["fixed_unsold_units"] > 0:
            expected_red = round(
                ((row["fixed_unsold_units"] - row["dynamic_unsold_units"]) / row["fixed_unsold_units"]) * 100.0,
                2,
            )
            assert abs(row["waste_reduction_pct"] - expected_red) <= 0.02
        else:
            assert row["waste_reduction_pct"] == 0.0


def test_financial_accounting_identities_hold_across_summaries(sample_inventory):
    """Verify that Gross Profit = Revenue - COGS and Net Profit = Gross Profit - Waste Loss."""
    # 1. Discount sensitivity table
    disc_df = evaluate_discount_sensitivity(sample_inventory)
    for _, row in disc_df.iterrows():
        assert abs(row["gross_profit"] - round(row["revenue"] - row["cogs"], 2)) <= 0.02
        assert abs(row["net_profit"] - round(row["gross_profit"] - row["waste_loss"], 2)) <= 0.02

    # 2. Elasticity sensitivity table
    elas_df = evaluate_elasticity_sensitivity(sample_inventory)
    for _, row in elas_df.iterrows():
        assert abs(row["gross_profit"] - round(row["revenue"] - row["cogs"], 2)) <= 0.02
        assert abs(row["net_profit"] - round(row["gross_profit"] - row["waste_loss"], 2)) <= 0.02


def test_performance_analysis_reproducible_and_deterministic(sample_inventory):
    """Verify that all Phase 3 evaluation functions produce identical results across runs."""
    cat_a = evaluate_category_performance(sample_inventory)
    cat_b = evaluate_category_performance(sample_inventory)
    pd.testing.assert_frame_equal(cat_a, cat_b)

    disc_a = evaluate_discount_sensitivity(sample_inventory)
    disc_b = evaluate_discount_sensitivity(sample_inventory)
    pd.testing.assert_frame_equal(disc_a, disc_b)

    elas_a = evaluate_elasticity_sensitivity(sample_inventory)
    elas_b = evaluate_elasticity_sensitivity(sample_inventory)
    pd.testing.assert_frame_equal(elas_a, elas_b)


def test_run_phase3_analysis_generates_all_files(sample_inventory, tmp_path: Path):
    """Verify full Phase 3 execution creates CSV files, Markdown report, and PNG charts."""
    out_data = tmp_path / "data"
    out_reports = tmp_path / "reports"

    outputs = run_phase3_analysis(
        inventory_path=DEFAULT_INVENTORY_FILE,
        output_data_dir=out_data,
        reports_dir=out_reports,
        generate_plot_images=True,
    )

    for name, filepath in outputs.items():
        assert filepath.exists(), f"Deliverable {name} not found at {filepath}"
        assert filepath.stat().st_size > 0, f"Deliverable {name} at {filepath} is empty"

    # Verify CSVs can be read back
    assert len(pd.read_csv(outputs["category_summary_csv"])) == 5
    assert len(pd.read_csv(outputs["discount_sensitivity_csv"])) == 5
    assert len(pd.read_csv(outputs["elasticity_sensitivity_csv"])) == 4
