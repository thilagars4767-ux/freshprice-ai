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
    save_dataframe_to_csv,
)
from src.pricing_engine import DEFAULT_INVENTORY_FILE, PricingPolicyConfig, load_inventory, simulate_inventory


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


def test_save_dataframe_to_csv_creates_missing_directory(tmp_path: Path):
    """Verify save_dataframe_to_csv creates parent directories automatically if missing."""
    nested_dir = tmp_path / "deep" / "nested" / "output_dir"
    target_csv = nested_dir / "test_summary.csv"

    assert not nested_dir.exists()
    test_df = pd.DataFrame({"col_a": [1, 2], "col_b": [3, 4]})
    saved_path = save_dataframe_to_csv(test_df, target_csv)

    assert nested_dir.exists()
    assert saved_path.exists()
    assert len(pd.read_csv(saved_path)) == 2


def test_save_dataframe_to_csv_permission_error_handling(tmp_path: Path, monkeypatch):
    """Verify clear, user-friendly PermissionError when a file is locked by Excel or another process."""
    target_csv = tmp_path / "locked_file.csv"
    test_df = pd.DataFrame({"a": [1]})

    def mock_to_csv(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(pd.DataFrame, "to_csv", mock_to_csv)

    with pytest.raises(PermissionError) as exc_info:
        save_dataframe_to_csv(test_df, target_csv)

    err_str = str(exc_info.value)
    # Check that error explains Excel lock and gives actionable instruction
    assert "Permission denied while attempting to write" in err_str
    assert "locked by Microsoft Excel" in err_str
    assert "Action Required: Please close the file in Excel" in err_str


def test_run_phase3_analysis_permission_error_propagation(tmp_path: Path, monkeypatch):
    """Verify run_phase3_analysis does NOT silently ignore PermissionError or report success."""
    out_data = tmp_path / "data"
    out_reports = tmp_path / "reports"

    def mock_to_csv(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(pd.DataFrame, "to_csv", mock_to_csv)

    with pytest.raises(PermissionError) as exc_info:
        run_phase3_analysis(
            inventory_path=DEFAULT_INVENTORY_FILE,
            output_data_dir=out_data,
            reports_dir=out_reports,
            generate_plot_images=False,
        )

    assert "locked by Microsoft Excel" in str(exc_info.value)


def test_discount_sensitivity_plateau_and_constraints(sample_inventory):
    """Verify why 30% and 35% discount caps produce identical results and respect constraints.

    Checks:
    1. 30% and 35% produce identical units sold, waste, revenue, and net profit.
    2. Across all caps, selling price is strictly >= unit_cost (price floor).
    3. Across all caps, discount_pct <= max_discount cap.
    """
    disc_df = evaluate_discount_sensitivity(sample_inventory, discount_caps=[0.10, 0.20, 0.30, 0.35])

    row_30 = disc_df.loc[disc_df["max_discount_setting"] == "30%"].iloc[0]
    row_35 = disc_df.loc[disc_df["max_discount_setting"] == "35%"].iloc[0]

    assert row_30["units_sold"] == row_35["units_sold"]
    assert row_30["unsold_units"] == row_35["unsold_units"]
    assert row_30["waste_rate_pct"] == row_35["waste_rate_pct"]
    assert row_30["revenue"] == row_35["revenue"]
    assert row_30["net_profit"] == row_35["net_profit"]

    # Verify constraint enforcement on individual batch recommendations across all caps
    for cap in [0.10, 0.20, 0.30, 0.35]:
        cfg = PricingPolicyConfig(max_discount=cap)
        res = simulate_inventory(sample_inventory, strategy="dynamic", config=cfg)

        # 1. Price floor: selling price >= unit cost (within rounding tolerance)
        assert (res["selling_price"] >= res["unit_cost"] - 1e-4).all()

        # 2. Max discount: discount_pct <= cap (within rounding tolerance)
        assert (res["discount_pct"] <= cap + 1e-3).all()


def test_elasticity_sensitivity_inelastic_safeguard(sample_inventory):
    """Verify that |Ed| <= 1.0 (inelastic & unitary elastic) produces results identical to fixed pricing.

    Ensures that when demand responsiveness is insufficient to offset margin dilution,
    the pricing engine's profitability safeguard retains regular prices.
    """
    fixed_res = simulate_inventory(sample_inventory, strategy="fixed")
    fixed_sold = round(float(fixed_res["units_sold"].sum()), 2)
    fixed_unsold = round(float(fixed_res["unsold_units"].sum()), 2)
    fixed_net = round(float(fixed_res["net_profit"].sum()), 2)

    elas_df = evaluate_elasticity_sensitivity(sample_inventory, elasticity_magnitudes=[0.5, 1.0, 1.5, 2.0])

    row_05 = elas_df.loc[elas_df["elasticity_magnitude"] == 0.5].iloc[0]
    row_10 = elas_df.loc[elas_df["elasticity_magnitude"] == 1.0].iloc[0]

    # At |Ed| = 0.5 and 1.0, dynamic results match fixed baseline identically
    assert row_05["units_sold"] == fixed_sold
    assert row_05["unsold_units"] == fixed_unsold
    assert row_05["net_profit"] == fixed_net
    assert row_05["waste_reduction_vs_fixed_pct"] == 0.0
    assert row_05["profit_diff_vs_fixed"] == 0.0

    assert row_10["units_sold"] == fixed_sold
    assert row_10["unsold_units"] == fixed_unsold
    assert row_10["net_profit"] == fixed_net
    assert row_10["waste_reduction_vs_fixed_pct"] == 0.0
    assert row_10["profit_diff_vs_fixed"] == 0.0


def test_sensitivity_physical_inventory_and_cost_reconciliation(sample_inventory):
    """Verify physical inventory conservation and total cost reconciliation across all summary rows."""
    total_stock = int(sample_inventory["initial_stock"].sum())
    total_initial_cost = round(float((sample_inventory["initial_stock"] * sample_inventory["unit_cost"]).sum()), 2)

    disc_df = evaluate_discount_sensitivity(sample_inventory)
    for _, row in disc_df.iterrows():
        # Inventory conservation: sold + unsold == total initial stock
        assert abs((row["units_sold"] + row["unsold_units"]) - total_stock) <= 1e-4
        # Cost reconciliation: COGS + waste loss == total initial inventory cost
        assert abs((row["cogs"] + row["waste_loss"]) - total_initial_cost) <= 0.02
        # Net profit identity: net_profit == revenue - total_initial_cost
        assert abs(row["net_profit"] - round(row["revenue"] - total_initial_cost, 2)) <= 0.02

    elas_df = evaluate_elasticity_sensitivity(sample_inventory)
    for _, row in elas_df.iterrows():
        assert abs((row["units_sold"] + row["unsold_units"]) - total_stock) <= 1e-4
        assert abs((row["cogs"] + row["waste_loss"]) - total_initial_cost) <= 0.02
        assert abs(row["net_profit"] - round(row["revenue"] - total_initial_cost, 2)) <= 0.02


def test_category_and_aggregate_reconciliation(sample_inventory):
    """Verify that category-level sums reconcile perfectly with aggregate summary tables."""
    cat_df = evaluate_category_performance(sample_inventory)
    disc_df = evaluate_discount_sensitivity(sample_inventory)

    # Category fixed totals vs aggregate fixed row
    fixed_row = disc_df.loc[disc_df["max_discount_setting"] == "Fixed (0%)"].iloc[0]
    assert abs(cat_df["fixed_units_sold"].sum() - fixed_row["units_sold"]) <= 0.01
    assert abs(cat_df["fixed_unsold_units"].sum() - fixed_row["unsold_units"]) <= 0.01
    assert abs(cat_df["fixed_revenue"].sum() - fixed_row["revenue"]) <= 0.01
    assert abs(cat_df["fixed_gross_profit"].sum() - fixed_row["gross_profit"]) <= 0.01
    assert abs(cat_df["fixed_waste_loss"].sum() - fixed_row["waste_loss"]) <= 0.01
    assert abs(cat_df["fixed_net_profit"].sum() - fixed_row["net_profit"]) <= 0.01

    # Category dynamic totals vs aggregate dynamic 35% row
    dyn_35_row = disc_df.loc[disc_df["max_discount_setting"] == "35%"].iloc[0]
    assert abs(cat_df["dynamic_units_sold"].sum() - dyn_35_row["units_sold"]) <= 0.01
    assert abs(cat_df["dynamic_unsold_units"].sum() - dyn_35_row["unsold_units"]) <= 0.01
    assert abs(cat_df["dynamic_revenue"].sum() - dyn_35_row["revenue"]) <= 0.01
    assert abs(cat_df["dynamic_gross_profit"].sum() - dyn_35_row["gross_profit"]) <= 0.01
    assert abs(cat_df["dynamic_waste_loss"].sum() - dyn_35_row["waste_loss"]) <= 0.01
    assert abs(cat_df["dynamic_net_profit"].sum() - dyn_35_row["net_profit"]) <= 0.01


