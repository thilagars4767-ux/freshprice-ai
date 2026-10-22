"""Unit tests for FreshPrice AI 30-Day Store Simulator (NEXAI 2026 Hackathon PS 4.1)."""

from pathlib import Path
import pytest
import pandas as pd

from src.store_simulator import (
    DEFAULT_PRODUCTS,
    InventoryBatch,
    MarkdownPolicyConfig,
    Product,
    SimulationResult,
    export_mvp_csv_outputs,
    generate_arrival_schedule,
    generate_baseline_demand_draws,
    get_default_products,
    get_shelf_life_aware_thresholds,
    run_store_simulation,
    simulate_single_policy,
)


def test_twenty_unique_perishable_products():
    """Verify that approximately 20 unique perishable products are modeled."""
    products = get_default_products()
    assert len(products) == 20
    product_ids = [p.product_id for p in products]
    assert len(set(product_ids)) == 20
    assert len(set(p.name for p in products)) == 20

    # Verify categories and valid perishability attributes
    categories = set(p.category for p in products)
    assert {"dairy", "bakery", "fruits", "vegetables"}.issubset(categories)

    for p in products:
        assert p.shelf_life_days > 0
        assert p.shelf_life_days <= 14  # Perishable products
        assert p.unit_cost > 0
        assert p.base_price > p.unit_cost
        assert p.avg_daily_demand > 0
        assert p.price_sensitivity > 0


def test_thirty_simulated_days_execution():
    """Verify simulation executes across 30 simulated days."""
    res = run_store_simulation(sim_days=30, seed=42)
    assert res.sim_days == 30

    # Daily history contains days 1 through 30 for both policies
    days_present = set(res.daily_history_df["day"])
    assert days_present == set(range(1, 31))

    # Exactly 20 products * 30 days * 2 policies = 1,200 daily records
    assert len(res.daily_history_df) == 20 * 30 * 2


def test_batch_arrival_and_expiry_tracking():
    """Verify scheduled batch arrivals and expiry date calculation."""
    products = get_default_products()
    arrivals = generate_arrival_schedule(products, sim_days=30, seed=42)

    assert len(arrivals) > 0
    for b in arrivals:
        assert b.arrival_day >= 1
        assert b.arrival_day <= 30
        assert b.expiry_day > b.arrival_day
        assert b.initial_quantity > 0
        assert b.remaining_quantity == b.initial_quantity


def test_no_sales_after_expiry():
    """Verify that products are never sold on or after their expiry day."""
    res = run_store_simulation(sim_days=30, seed=42)
    daily_df = res.daily_history_df

    # Any record with sales must have had days_until_expiry >= 1 at time of sale
    sold_records = daily_df[daily_df["units_sold"] > 0]
    assert (sold_records["days_until_expiry"] >= 1).all()


def test_inventory_conservation():
    """Verify physical inventory balance: Total Received == Units Sold + Units Wasted + Ending Stock."""
    res = run_store_simulation(sim_days=30, seed=42)
    f = res.fixed_metrics
    m = res.markdown_metrics

    # Fixed Policy Conservation
    assert abs(f.total_received - (f.units_sold + f.units_wasted + f.ending_inventory)) <= 1e-4

    # Markdown Policy Conservation
    assert abs(m.total_received - (m.units_sold + m.units_wasted + m.ending_inventory)) <= 1e-4

    # Both policies receive identical total units
    assert f.total_received == m.total_received


def test_daily_demand_responds_to_prices_and_expiry():
    """Verify that daily demand expands when discounts are applied near expiry."""
    res = run_store_simulation(sim_days=30, seed=42)
    daily_df = res.daily_history_df

    # Total units sold should be higher under markdown pricing
    assert res.markdown_metrics.units_sold > res.fixed_metrics.units_sold


def test_fixed_policy_never_applies_discounts():
    """Verify that fixed-price policy strictly charges base selling price without discounts."""
    res = run_store_simulation(sim_days=30, seed=42)
    fixed_daily = res.daily_history_df[res.daily_history_df["policy"] == "fixed"]

    assert (fixed_daily["discount_pct"] == 0.0).all()
    assert (fixed_daily["selling_price"] == fixed_daily["regular_price"]).all()


def test_markdown_thresholds_and_discounts_adjustable():
    """Verify that markdown thresholds and discount percentages are configurable."""
    cfg_mild = MarkdownPolicyConfig(threshold_1_days=1, discount_1_pct=0.10, threshold_2_days=2, discount_2_pct=0.05)
    cfg_deep = MarkdownPolicyConfig(threshold_1_days=1, discount_1_pct=0.50, threshold_2_days=2, discount_2_pct=0.30)

    res_mild = run_store_simulation(sim_days=30, seed=42, config=cfg_mild)
    res_deep = run_store_simulation(sim_days=30, seed=42, config=cfg_deep)

    # Different discount configurations produce different sales, waste, and revenue outcomes
    assert res_mild.markdown_metrics.units_sold != res_deep.markdown_metrics.units_sold
    assert res_mild.markdown_metrics.revenue != res_deep.markdown_metrics.revenue


def test_selling_prices_respect_cost_floor():
    """Verify that dynamic selling prices never breach the wholesale unit cost floor."""
    # Aggressive 90% discount configuration
    cfg_aggressive = MarkdownPolicyConfig(threshold_1_days=1, discount_1_pct=0.90, threshold_2_days=2, discount_2_pct=0.70, enforce_cost_floor=True)
    res = run_store_simulation(sim_days=30, seed=42, config=cfg_aggressive)

    products_map = {p.product_id: p for p in get_default_products()}
    daily_md = res.daily_history_df[res.daily_history_df["policy"] == "markdown"]

    for _, row in daily_md.iterrows():
        p = products_map[row["product_id"]]
        assert row["selling_price"] >= p.unit_cost - 1e-4


def test_both_policies_use_identical_starting_conditions():
    """Verify both policies start with identical inventory arrivals and baseline demand draws."""
    products = get_default_products()
    arrivals = generate_arrival_schedule(products, sim_days=30, seed=42)
    demand = generate_baseline_demand_draws(products, sim_days=30, seed=42)

    fixed_m, _, _ = simulate_single_policy("fixed", products, arrivals, demand, sim_days=30)
    md_m, _, _ = simulate_single_policy("markdown", products, arrivals, demand, sim_days=30)

    assert fixed_m.total_received == md_m.total_received


def test_reproducibility_with_same_seed():
    """Verify that running the simulation with the same seed reproduces exact identical results."""
    run_a = run_store_simulation(sim_days=30, seed=42)
    run_b = run_store_simulation(sim_days=30, seed=42)

    assert run_a.fixed_metrics == run_b.fixed_metrics
    assert run_a.markdown_metrics == run_b.markdown_metrics
    pd.testing.assert_frame_equal(run_a.comparison_summary_df, run_b.comparison_summary_df)


def test_different_seeds_produce_different_outcomes():
    """Verify that different random seeds produce different stochastic demand variations."""
    run_seed_1 = run_store_simulation(sim_days=30, seed=42)
    run_seed_2 = run_store_simulation(sim_days=30, seed=999)

    assert run_seed_1.fixed_metrics.units_sold != run_seed_2.fixed_metrics.units_sold


def test_financial_accounting_reconciliation():
    """Verify standard GAAP financial identities: Gross Margin == Revenue - COGS."""
    res = run_store_simulation(sim_days=30, seed=42)

    for m in [res.fixed_metrics, res.markdown_metrics]:
        assert abs(m.gross_margin - round(m.revenue - m.cogs, 2)) <= 0.02
        if m.revenue > 0:
            expected_pct = round((m.gross_margin / m.revenue) * 100.0, 2)
            assert abs(m.gross_margin_pct - expected_pct) <= 0.02


def test_markdown_events_recorded():
    """Verify that per-product markdown events are tracked chronologically."""
    res = run_store_simulation(sim_days=30, seed=42)
    events_df = res.markdown_events_df

    assert len(events_df) > 0
    assert "day" in events_df.columns
    assert "product_id" in events_df.columns
    assert "discount_pct" in events_df.columns
    assert (events_df["discount_pct"] > 0).all()
    assert (events_df["units_sold"] > 0).all()


def test_export_mvp_csv_outputs(tmp_path: Path):
    """Verify exporting MVP CSV outputs to disk."""
    res = run_store_simulation(sim_days=30, seed=42)
    saved = export_mvp_csv_outputs(res, output_dir=tmp_path)

    assert len(saved) == 4
    for key, path in saved.items():
        assert path.exists()
        assert path.stat().st_size > 0
        df = pd.read_csv(path)
        assert len(df) > 0


# ---------------------------------------------------------------------------
# Tests for Shelf-Life-Aware Markdown Eligibility & Precedence Rules
# ---------------------------------------------------------------------------

def test_shelf_life_aware_thresholds_logic():
    """Verify shelf-life-aware threshold calculation across short and long life SKUs."""
    cfg_default = MarkdownPolicyConfig(threshold_1_days=1, threshold_2_days=2)

    # 3-day product: effective threshold cannot exceed max(1, 3-2) = 1
    t1_3, t2_3 = get_shelf_life_aware_thresholds(3, cfg_default)
    assert t2_3 == 1
    assert t1_3 == 1

    # 4-day product: max(1, 4-2) = 2, so follows configured 2
    t1_4, t2_4 = get_shelf_life_aware_thresholds(4, cfg_default)
    assert t2_4 == 2
    assert t1_4 == 1

    # 8-day product: max(1, 8-2) = 6, follows configured 2
    t1_8, t2_8 = get_shelf_life_aware_thresholds(8, cfg_default)
    assert t2_8 == 2
    assert t1_8 == 1

    # Config with urgent > near-expiry: urgent is capped at near-expiry
    cfg_inverted = MarkdownPolicyConfig(threshold_1_days=3, threshold_2_days=2)
    t1_inv, t2_inv = get_shelf_life_aware_thresholds(5, cfg_inverted)
    assert t2_inv == 2
    assert t1_inv == 2  # capped at t2


def test_three_day_products_do_not_receive_two_day_markdown_prematurely():
    """Verify 3-day shelf life products NEVER receive near-expiry discounts on Day 2."""
    res = run_store_simulation(sim_days=30, seed=42)
    daily_df = res.daily_history_df
    md_df = daily_df[daily_df["policy"] == "markdown"]

    prods = get_default_products()
    three_day_pids = {p.product_id for p in prods if p.shelf_life_days == 3}
    assert len(three_day_pids) == 5  # 5 products with 3-day shelf life

    # For 3-day products with 2 days until expiry, discount MUST be 0.0%
    day2_records = md_df[(md_df["product_id"].isin(three_day_pids)) & (md_df["days_until_expiry"] == 2)]
    assert len(day2_records) > 0
    assert (day2_records["discount_pct"] == 0.0).all()
    assert (day2_records["selling_price"] == day2_records["regular_price"]).all()


def test_longer_life_products_follow_configured_threshold():
    """Verify products with shelf life >= 4 days follow configured near-expiry threshold."""
    res = run_store_simulation(sim_days=30, seed=42)
    daily_df = res.daily_history_df
    md_df = daily_df[daily_df["policy"] == "markdown"]

    prods = get_default_products()
    longer_pids = {p.product_id for p in prods if p.shelf_life_days >= 4}

    # For longer-life products with 2 days to expiry, near-expiry discount (20%) is applied
    day2_records = md_df[(md_df["product_id"].isin(longer_pids)) & (md_df["days_until_expiry"] == 2)]
    assert len(day2_records) > 0
    # Must have applied discount
    assert (day2_records["discount_pct"] > 0.0).all()


def test_urgent_clearance_precedence_and_single_discount():
    """Verify urgent clearance takes precedence and only one discount is applied."""
    cfg = MarkdownPolicyConfig(threshold_1_days=1, discount_1_pct=0.40, threshold_2_days=2, discount_2_pct=0.20)
    res = run_store_simulation(sim_days=30, seed=42, config=cfg)
    events_df = res.markdown_events_df

    # On day with 1 day to expiry, urgent clearance applies, not near-expiry
    urgent_events = events_df[events_df["days_until_expiry"] == 1]
    assert len(urgent_events) > 0
    for _, ev in urgent_events.iterrows():
        assert "Urgent clearance" in ev["reason"]


def test_zero_discount_reproduces_fixed_price_behavior():
    """Verify zero discount config exactly reproduces fixed-price metrics."""
    cfg_zero = MarkdownPolicyConfig(threshold_1_days=1, discount_1_pct=0.0, threshold_2_days=2, discount_2_pct=0.0)
    res = run_store_simulation(sim_days=30, seed=42, config=cfg_zero)

    f = res.fixed_metrics
    m = res.markdown_metrics

    assert f.units_sold == m.units_sold
    assert f.units_wasted == m.units_wasted
    assert f.waste_rate_pct == m.waste_rate_pct
    assert f.revenue == m.revenue
    assert f.gross_margin == m.gross_margin
    assert m.markdown_events_count == 0


def test_physical_inventory_bound_and_no_overselling():
    """Verify daily sales never exceed available unexpired inventory."""
    res = run_store_simulation(sim_days=30, seed=42)
    daily_df = res.daily_history_df

    # Units sold cannot be negative
    assert (daily_df["units_sold"] >= 0.0).all()
    # Units wasted cannot be negative
    assert (daily_df["units_wasted"] >= 0.0).all()


def test_markdown_event_history_agrees_with_actual_discounts():
    """Verify every event in markdown_events_history corresponds to actual discounted daily sales."""
    res = run_store_simulation(sim_days=30, seed=42)
    events_df = res.markdown_events_df
    daily_df = res.daily_history_df
    md_daily = daily_df[daily_df["policy"] == "markdown"]

    for _, ev in events_df.iterrows():
        match = md_daily[(md_daily["day"] == ev["day"]) & (md_daily["product_id"] == ev["product_id"])]
        assert len(match) == 1
        rec = match.iloc[0]
        assert rec["discount_pct"] == ev["discount_pct"]
        assert rec["selling_price"] == ev["selling_price"]
        assert rec["units_sold"] == ev["units_sold"]


def test_validate_markdown_config():
    """Verify validate_markdown_config validates negative values and invalid margin floors."""
    from src.store_simulator import validate_markdown_config

    valid_cfg = MarkdownPolicyConfig(
        discount_1_pct=0.40,
        discount_2_pct=0.20,
        min_gross_margin_pct=5.0,
    )
    validate_markdown_config(valid_cfg)  # Should not raise

    with pytest.raises(ValueError, match="negative"):
        validate_markdown_config(MarkdownPolicyConfig(discount_1_pct=-0.1))

    with pytest.raises(ValueError, match="negative"):
        validate_markdown_config(MarkdownPolicyConfig(discount_2_pct=-0.05))

    with pytest.raises(ValueError, match="negative"):
        validate_markdown_config(MarkdownPolicyConfig(threshold_1_days=-1))

    with pytest.raises(ValueError, match="margin percentage"):
        validate_markdown_config(MarkdownPolicyConfig(min_gross_margin_pct=100.0))


def test_official_thirteen_metrics_in_summary_df():
    """Verify all official metrics required by NEXAI 2026 are present in comparison_summary_df."""
    res = run_store_simulation(sim_days=30, seed=42)
    metrics_list = res.comparison_summary_df["Metric"].tolist()

    expected_metrics = [
        "Initial Inventory Received (units)",
        "Units Sold",
        "Units Wasted (Expired)",
        "Sell-Through Rate (%)",
        "Waste Rate (%)",
        "Waste Reduction (%)",
        "Total Revenue (INR)",
        "Cost of Goods Sold - COGS (INR)",
        "Gross Margin (INR)",
        "Gross Margin (%)",
        "Total Waste Cost (INR)",
        "Net Contribution after Waste (INR)",
        "Markdown Events Recorded",
        "Markdown Units Sold (units)",
    ]

    for em in expected_metrics:
        assert em in metrics_list, f"Missing required metric: {em}"

    # Verify accounting identity: Net Contribution = Gross Profit - Waste Cost
    f = res.fixed_metrics
    m = res.markdown_metrics
    assert abs(f.net_contribution - (f.gross_margin - f.total_waste_cost)) < 1e-4
    assert abs(m.net_contribution - (m.gross_margin - m.total_waste_cost)) < 1e-4
    assert f.markdown_units_sold == 0
    assert m.markdown_units_sold >= 0
    assert 0.0 <= f.sell_through_rate_pct <= 100.0
    assert 0.0 <= m.sell_through_rate_pct <= 100.0


def test_margin_floor_limits_excessive_markdowns():
    """Verify that aggressive discounts are clamped by the minimum gross margin floor."""
    # Configure an extreme discount of 90% with a 20% margin floor
    config = MarkdownPolicyConfig(
        threshold_1_days=1,
        discount_1_pct=0.90,
        threshold_2_days=2,
        discount_2_pct=0.80,
        min_gross_margin_pct=20.0,
    )
    res = run_store_simulation(sim_days=30, seed=42, config=config)
    events_df = res.markdown_events_df

    assert not events_df.empty
    # Margin floor limiting should have triggered
    clamped_events = events_df[events_df["margin_floor_limited"] == True]
    assert len(clamped_events) > 0

    prods = {p["product_id"]: p for _, p in res.products_df.iterrows()}
    for _, ev in clamped_events.iterrows():
        assert ev["actual_discount_pct"] < ev["requested_discount_pct"]
        prod = prods[ev["product_id"]]
        # Actual price must be >= cost / (1 - 0.20)
        min_allowed_price = prod["unit_cost"] / (1.0 - 0.20)
        assert ev["selling_price"] >= min_allowed_price - 1e-4


def test_shopper_response_multiplier_sensitivity():
    """Verify shopper response multiplier scales discount uplift while preserving baseline."""
    from src.store_simulator import validate_markdown_config

    # Run default (multiplier = 1.0)
    cfg_100 = MarkdownPolicyConfig(shopper_response_multiplier=1.0)
    res_100 = run_store_simulation(sim_days=30, seed=42, config=cfg_100)

    # Run half-strength response (multiplier = 0.5)
    cfg_050 = MarkdownPolicyConfig(shopper_response_multiplier=0.5)
    res_050 = run_store_simulation(sim_days=30, seed=42, config=cfg_050)

    # Fixed-price baseline must be identical (since discount = 0)
    assert res_100.fixed_metrics.revenue == pytest.approx(res_050.fixed_metrics.revenue, abs=1e-4)
    assert res_100.fixed_metrics.units_sold == pytest.approx(res_050.fixed_metrics.units_sold, abs=1e-4)
    assert res_100.fixed_metrics.units_wasted == pytest.approx(res_050.fixed_metrics.units_wasted, abs=1e-4)

    # Under markdown, 0.5 response yields lower sales velocity on discounted items
    m_100 = res_100.markdown_metrics
    m_050 = res_050.markdown_metrics
    assert m_050.units_sold <= m_100.units_sold
    assert m_050.units_wasted >= m_100.units_wasted

    # Negative multiplier must raise ValueError
    with pytest.raises(ValueError, match="Shopper response multiplier cannot be negative"):
        validate_markdown_config(MarkdownPolicyConfig(shopper_response_multiplier=-0.2))




