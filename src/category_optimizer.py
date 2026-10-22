"""Category-Specific Markdown Optimizer (NEXAI 2026 Hackathon PS 4.1 Stretch Goal).

Evaluates candidate markdown schedules per product category (Dairy, Bakery, Fruits, Vegetables)
across matched simulation seeds, optimizing for Net Contribution after Waste Cost while
strictly enforcing wholesale cost / margin floors and zero sales after expiry.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from src.store_simulator import (
    InventoryBatch,
    MarkdownPolicyConfig,
    Product,
    SimulationResult,
    generate_arrival_schedule,
    generate_baseline_demand_draws,
    get_default_products,
    run_store_simulation,
    simulate_single_policy,
)


@dataclass
class CategoryCandidateSchedule:
    """A candidate clearance markdown schedule for a product category."""
    schedule_id: str
    schedule_name: str
    urgent_days_threshold: int
    urgent_discount_pct: float
    near_expiry_days_threshold: int
    near_expiry_discount_pct: float

    @property
    def label(self) -> str:
        u_pct = int(round(self.urgent_discount_pct * 100))
        n_pct = int(round(self.near_expiry_discount_pct * 100))
        return f"≤{self.urgent_days_threshold}d: {u_pct}% | ≤{self.near_expiry_days_threshold}d: {n_pct}%"


# Standard candidate schedules to evaluate per category
DEFAULT_CANDIDATE_SCHEDULES: List[CategoryCandidateSchedule] = [
    CategoryCandidateSchedule("SCHED-CONSERVATIVE", "Conservative Clearance", 1, 0.20, 2, 0.10),
    CategoryCandidateSchedule("SCHED-MODERATE", "Moderate Balanced", 1, 0.30, 2, 0.15),
    CategoryCandidateSchedule("SCHED-AGGRESSIVE", "Aggressive Clearance", 1, 0.40, 2, 0.20),
    CategoryCandidateSchedule("SCHED-DEEP", "Deep Salvage Clearance", 1, 0.50, 2, 0.25),
]


@dataclass
class CategoryEvaluationResult:
    """Evaluation summary for a category candidate schedule across evaluation seeds."""
    category: str
    schedule_id: str
    schedule_name: str
    urgent_threshold: int
    urgent_discount_pct: float
    near_threshold: int
    near_discount_pct: float
    avg_revenue: float
    avg_cogs: float
    avg_gross_profit: float
    avg_gross_margin_pct: float
    avg_units_sold: float
    avg_units_wasted: float
    avg_waste_cost: float
    avg_net_contribution: float
    avg_sell_through_pct: float
    avg_ending_stock: float
    is_best_strategy: bool = False


@dataclass
class CategoryOptimizationReport:
    """Complete multi-category optimization deliverable comparing candidates against baselines."""
    eval_seeds: List[int]
    sim_days: int
    min_margin_pct: float
    all_evaluations: List[CategoryEvaluationResult]
    best_schedule_per_category: Dict[str, CategoryCandidateSchedule]
    composite_category_configs: Dict[str, Tuple[int, float, int, float]]
    baseline_fixed_net_contribution: float
    default_markdown_net_contribution: float
    optimized_category_net_contribution: float
    net_contribution_gain_over_baseline: float
    net_contribution_gain_over_default: float

    @property
    def summary_df(self) -> pd.DataFrame:
        """Tabular summary of all evaluated category strategies."""
        records = []
        for r in self.all_evaluations:
            records.append({
                "Category": r.category.title(),
                "Schedule": r.schedule_name,
                "Clearance Rules": f"≤{r.urgent_threshold}d: {int(r.urgent_discount_pct*100)}% | ≤{r.near_threshold}d: {int(r.near_discount_pct*100)}%",
                "Avg Revenue (₹)": round(r.avg_revenue, 2),
                "Avg Gross Profit (₹)": round(r.avg_gross_profit, 2),
                "Avg Gross Margin %": f"{r.avg_gross_margin_pct:.2f}%",
                "Avg Waste (Units)": round(r.avg_units_wasted, 1),
                "Avg Waste Cost (₹)": round(r.avg_waste_cost, 2),
                "Avg Net Contribution (₹)": round(r.avg_net_contribution, 2),
                "Avg Sell-Through %": f"{r.avg_sell_through_pct:.2f}%",
                "Optimal Choice": "★ BEST STRATEGY" if r.is_best_strategy else "",
            })
        return pd.DataFrame(records)


def discover_categories(products: Optional[List[Product]] = None) -> List[str]:
    """Discover unique product categories dynamically from the catalog."""
    if products is None:
        products = get_default_products()
    return sorted(list({p.category for p in products}))


def evaluate_category_strategy_across_seeds(
    category: str,
    schedule: CategoryCandidateSchedule,
    seeds: List[int],
    sim_days: int = 30,
    min_margin_pct: float = 0.0,
    products: Optional[List[Product]] = None,
) -> CategoryEvaluationResult:
    """Evaluate a single candidate schedule for a single category across multiple seeds."""
    if products is None:
        products = get_default_products()

    cat_products = [p for p in products if p.category == category]

    rev_list, cogs_list, gp_list, sold_list, wasted_list = [], [], [], [], []
    waste_cost_list, net_contrib_list, received_list, ending_list = [], [], [], []

    cat_config_dict = {
        category: (
            schedule.urgent_days_threshold,
            schedule.urgent_discount_pct,
            schedule.near_expiry_days_threshold,
            schedule.near_expiry_discount_pct,
        )
    }

    config = MarkdownPolicyConfig(
        threshold_1_days=schedule.urgent_days_threshold,
        discount_1_pct=schedule.urgent_discount_pct,
        threshold_2_days=schedule.near_expiry_days_threshold,
        discount_2_pct=schedule.near_expiry_discount_pct,
        min_gross_margin_pct=min_margin_pct,
        category_configs=cat_config_dict,
    )

    for s in seeds:
        arrivals = generate_arrival_schedule(products, sim_days=sim_days, seed=s)
        demand_draws = generate_baseline_demand_draws(products, sim_days=sim_days, seed=s)

        metrics, daily, _ = simulate_single_policy(
            policy_name="markdown",
            products=products,
            arrival_batches=arrivals,
            baseline_demand=demand_draws,
            sim_days=sim_days,
            config=config,
        )

        # Filter metrics specifically for the target category
        cat_daily = [r for r in daily if r.category == category]
        cat_rev = sum(r.revenue for r in cat_daily)
        cat_cogs = sum(r.cogs for r in cat_daily)
        cat_gp = cat_rev - cat_cogs
        cat_sold = sum(r.units_sold for r in cat_daily)
        cat_wasted = sum(r.units_wasted for r in cat_daily)
        cat_waste_cost = sum(r.waste_cost for r in cat_daily)
        cat_net_contrib = cat_gp - cat_waste_cost
        cat_ending = sum(r.ending_stock for r in cat_daily if r.day == sim_days)
        cat_received = sum(b.initial_quantity for b in arrivals if b.product_id in {p.product_id for p in cat_products})

        rev_list.append(cat_rev)
        cogs_list.append(cat_cogs)
        gp_list.append(cat_gp)
        sold_list.append(cat_sold)
        wasted_list.append(cat_wasted)
        waste_cost_list.append(cat_waste_cost)
        net_contrib_list.append(cat_net_contrib)
        received_list.append(cat_received)
        ending_list.append(cat_ending)

    avg_rev = float(np.mean(rev_list))
    avg_cogs = float(np.mean(cogs_list))
    avg_gp = float(np.mean(gp_list))
    avg_sold = float(np.mean(sold_list))
    avg_wasted = float(np.mean(wasted_list))
    avg_waste_cost = float(np.mean(waste_cost_list))
    avg_net_contrib = float(np.mean(net_contrib_list))
    avg_received = float(np.mean(received_list))
    avg_ending = float(np.mean(ending_list))

    avg_gm_pct = (avg_gp / avg_rev * 100.0) if avg_rev > 0 else 0.0
    avg_str_pct = (avg_sold / avg_received * 100.0) if avg_received > 0 else 0.0

    return CategoryEvaluationResult(
        category=category,
        schedule_id=schedule.schedule_id,
        schedule_name=schedule.schedule_name,
        urgent_threshold=schedule.urgent_days_threshold,
        urgent_discount_pct=schedule.urgent_discount_pct,
        near_threshold=schedule.near_expiry_days_threshold,
        near_discount_pct=schedule.near_expiry_discount_pct,
        avg_revenue=avg_rev,
        avg_cogs=avg_cogs,
        avg_gross_profit=avg_gp,
        avg_gross_margin_pct=avg_gm_pct,
        avg_units_sold=avg_sold,
        avg_units_wasted=avg_wasted,
        avg_waste_cost=avg_waste_cost,
        avg_net_contribution=avg_net_contrib,
        avg_sell_through_pct=avg_str_pct,
        avg_ending_stock=avg_ending,
    )


def run_category_optimization(
    seeds: Optional[List[int]] = None,
    sim_days: int = 30,
    min_margin_pct: float = 0.0,
    candidate_schedules: Optional[List[CategoryCandidateSchedule]] = None,
    products: Optional[List[Product]] = None,
) -> CategoryOptimizationReport:
    """Run complete category-specific markdown optimization across all catalog categories.

    Evaluates each candidate schedule per category across multiple evaluation seeds,
    selecting the schedule that maximizes Net Contribution after Waste Cost.
    """
    if seeds is None:
        seeds = [42, 101, 2026]
    if candidate_schedules is None:
        candidate_schedules = DEFAULT_CANDIDATE_SCHEDULES
    if products is None:
        products = get_default_products()

    categories = discover_categories(products)
    all_evaluations: List[CategoryEvaluationResult] = []
    best_schedules: Dict[str, CategoryCandidateSchedule] = {}
    composite_configs: Dict[str, Tuple[int, float, int, float]] = {}

    for cat in categories:
        cat_results: List[CategoryEvaluationResult] = []
        for sched in candidate_schedules:
            res = evaluate_category_strategy_across_seeds(
                category=cat,
                schedule=sched,
                seeds=seeds,
                sim_days=sim_days,
                min_margin_pct=min_margin_pct,
                products=products,
            )
            cat_results.append(res)

        # Primary Objective: Maximize Average Net Contribution after Waste Cost
        cat_results.sort(key=lambda r: r.avg_net_contribution, reverse=True)
        cat_results[0].is_best_strategy = True
        best_eval = cat_results[0]

        best_sched = next(s for s in candidate_schedules if s.schedule_id == best_eval.schedule_id)
        best_schedules[cat] = best_sched
        composite_configs[cat] = (
            best_sched.urgent_days_threshold,
            best_sched.urgent_discount_pct,
            best_sched.near_expiry_days_threshold,
            best_sched.near_expiry_discount_pct,
        )
        all_evaluations.extend(cat_results)

    # Global Benchmark Comparisons (Fixed Baseline vs Default Markdown vs Optimized Category)
    fixed_net_contribs, default_net_contribs, opt_net_contribs = [], [], []

    for s in seeds:
        # Fixed
        res_f = run_store_simulation(sim_days=sim_days, seed=s)
        fixed_net_contribs.append(res_f.fixed_metrics.net_contribution)
        # Default Markdown (40% / 20%)
        default_net_contribs.append(res_f.markdown_metrics.net_contribution)
        # Optimized Category Config
        opt_cfg = MarkdownPolicyConfig(
            min_gross_margin_pct=min_margin_pct,
            category_configs=composite_configs,
        )
        res_opt = run_store_simulation(sim_days=sim_days, seed=s, config=opt_cfg)
        opt_net_contribs.append(res_opt.markdown_metrics.net_contribution)

    avg_fixed_net = float(np.mean(fixed_net_contribs))
    avg_default_net = float(np.mean(default_net_contribs))
    avg_opt_net = float(np.mean(opt_net_contribs))

    return CategoryOptimizationReport(
        eval_seeds=seeds,
        sim_days=sim_days,
        min_margin_pct=min_margin_pct,
        all_evaluations=all_evaluations,
        best_schedule_per_category=best_schedules,
        composite_category_configs=composite_configs,
        baseline_fixed_net_contribution=round(avg_fixed_net, 2),
        default_markdown_net_contribution=round(avg_default_net, 2),
        optimized_category_net_contribution=round(avg_opt_net, 2),
        net_contribution_gain_over_baseline=round(avg_opt_net - avg_fixed_net, 2),
        net_contribution_gain_over_default=round(avg_opt_net - avg_default_net, 2),
    )
