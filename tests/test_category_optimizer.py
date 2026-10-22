"""Unit tests for FreshPrice AI Category-Specific Markdown Optimizer (PS 4.1 Stretch Goal)."""

import pytest
import pandas as pd
from src.category_optimizer import (
    DEFAULT_CANDIDATE_SCHEDULES,
    CategoryCandidateSchedule,
    CategoryOptimizationReport,
    discover_categories,
    evaluate_category_strategy_across_seeds,
    run_category_optimization,
)
from src.store_simulator import get_default_products


def test_discover_categories():
    """Verify category optimizer discovers exact catalog categories."""
    categories = discover_categories()
    assert len(categories) == 4
    assert set(categories) == {"bakery", "dairy", "fruits", "vegetables"}


def test_candidate_schedules_defined():
    """Verify default candidate clearance schedules are valid."""
    assert len(DEFAULT_CANDIDATE_SCHEDULES) >= 3
    for s in DEFAULT_CANDIDATE_SCHEDULES:
        assert s.urgent_days_threshold > 0
        assert 0.0 < s.urgent_discount_pct <= 1.0
        assert s.near_expiry_days_threshold >= s.urgent_days_threshold
        assert 0.0 <= s.near_expiry_discount_pct <= s.urgent_discount_pct


def test_evaluate_single_category_strategy():
    """Verify evaluation of a candidate schedule yields consistent accounting metrics."""
    sched = DEFAULT_CANDIDATE_SCHEDULES[1]  # Moderate
    res = evaluate_category_strategy_across_seeds(
        category="dairy",
        schedule=sched,
        seeds=[42, 101],
        sim_days=15,
        min_margin_pct=5.0,
    )
    assert res.category == "dairy"
    assert res.avg_revenue > 0.0
    assert res.avg_cogs > 0.0
    assert res.avg_gross_profit == pytest.approx(res.avg_revenue - res.avg_cogs, abs=0.5)
    assert res.avg_net_contribution == pytest.approx(res.avg_gross_profit - res.avg_waste_cost, abs=0.5)
    assert 0.0 <= res.avg_sell_through_pct <= 100.0


def test_run_category_optimization_complete():
    """Verify end-to-end multi-category optimization selects best schedules and generates report."""
    # Fast 15-day evaluation on 2 seeds for testing
    report = run_category_optimization(
        seeds=[42, 101],
        sim_days=15,
        min_margin_pct=0.0,
        candidate_schedules=DEFAULT_CANDIDATE_SCHEDULES[:3],
    )
    assert isinstance(report, CategoryOptimizationReport)
    assert len(report.best_schedule_per_category) == 4
    for cat in ["bakery", "dairy", "fruits", "vegetables"]:
        assert cat in report.best_schedule_per_category
        assert cat in report.composite_category_configs
        t1, d1, t2, d2 = report.composite_category_configs[cat]
        assert t1 >= 1 and t2 >= 1
        assert 0.0 <= d1 <= 1.0 and 0.0 <= d2 <= 1.0

    # Summary table format
    df = report.summary_df
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Optimal Choice" in df.columns
    best_rows = df[df["Optimal Choice"] == "★ BEST STRATEGY"]
    assert len(best_rows) == 4  # Exactly one best strategy per category

    # Financial reporting
    assert report.baseline_fixed_net_contribution > 0.0
    assert report.optimized_category_net_contribution > 0.0
