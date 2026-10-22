"""FreshPrice AI — Individual Product Discount Optimizer.

NEXAI 2026 Hackathon (PS 4.1: Track 4 Grocery Retail).

This module evaluates candidate markdown discounts (0%, 5%, 10%, 15%, 20%, 30%, 40%)
for individual perishable grocery products. It selects the optimal discount that balances
expected gross profit and food waste reduction while strictly enforcing a configurable
minimum gross-margin percentage floor:

    minimum_price = unit_cost / (1 - min_margin)

Any candidate discount whose rounded selling price falls below minimum_price is rejected.
Unnecessary discounts are prevented when stock is projected to sell out naturally before expiry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.demand_estimator import ProductDemandProfile
from src.store_simulator import Product

# Standard candidate discounts evaluated for clearance
CANDIDATE_DISCOUNTS: Tuple[float, ...] = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40)


@dataclass(frozen=True)
class CandidateEvaluation:
    """Detailed evaluation of a single candidate discount percentage."""
    discount_pct: float
    selling_price: float
    is_feasible: bool
    rejection_reason: Optional[str]
    expected_demand: float
    expected_units_sold: float
    expected_units_wasted: float
    expected_revenue: float
    expected_cogs: float
    expected_gross_profit: float
    expected_gross_margin_pct: float
    net_objective_value: float


@dataclass(frozen=True)
class DiscountRecommendation:
    """Optimal markdown pricing recommendation for a single product."""
    product_id: str
    product_name: str
    category: str
    historical_avg_daily_demand: float
    current_stock: float
    days_to_expiry: int
    recommended_discount_pct: float
    recommended_selling_price: float
    expected_units_sold: float
    expected_units_wasted: float
    expected_revenue: float
    expected_gross_profit: float
    expected_gross_margin_pct: float
    minimum_margin_requirement_pct: float
    minimum_acceptable_price: float
    recommendation_explanation: str
    sensitivity_source: str
    price_sensitivity_used: float
    is_discounted: bool
    candidate_evaluations: List[CandidateEvaluation]


def compute_minimum_acceptable_price(unit_cost: float, min_margin_pct: float) -> float:
    """Calculate the minimum price required to achieve the target gross margin percentage.

    Formula:
        minimum_price = unit_cost / (1.0 - m)
        where m = min_margin_pct / 100.0

    Parameters
    ----------
    unit_cost : float
        Wholesale unit acquisition cost (C).
    min_margin_pct : float
        Target minimum gross margin percentage (e.g. 15.0 for 15%).

    Returns
    -------
    float
        Rounded minimum acceptable selling price.

    Raises
    ------
    ValueError
        If min_margin_pct >= 100% for positive unit costs.
    """
    m = min_margin_pct / 100.0 if min_margin_pct > 1.0 else min_margin_pct
    if m >= 0.999:
        if unit_cost > 0:
            raise ValueError(
                f"A gross margin requirement of {min_margin_pct:.1f}% is mathematically impossible "
                f"for positive unit cost (C = ₹{unit_cost:.2f}). Required price would approach infinity."
            )
        return 0.0

    if m < 0.0:
        m = 0.0

    raw_min_price = unit_cost / (1.0 - m)
    return round(raw_min_price, 2)


class DiscountOptimizer:
    """Optimizes candidate clearance markdowns for individual products."""

    def __init__(
        self,
        candidate_discounts: Optional[Tuple[float, ...]] = None,
        default_min_margin_pct: float = 0.0,
        waste_disposal_fee_per_unit: float = 0.0,
    ) -> None:
        """Initialize the DiscountOptimizer.

        Parameters
        ----------
        candidate_discounts : Optional[Tuple[float, ...]]
            List of markdown candidate fractions, default (0%, 5%, 10%, 15%, 20%, 30%, 40%).
        default_min_margin_pct : float
            Configurable minimum gross-margin percentage (e.g. 0.0% for wholesale cost floor,
            or 10.0% for 10% gross margin protection).
        waste_disposal_fee_per_unit : float
            Configurable physical waste disposal penalty in INR per wasted unit, default ₹0.00.
        """
        self.candidate_discounts = candidate_discounts or CANDIDATE_DISCOUNTS
        self.default_min_margin_pct = default_min_margin_pct
        self.waste_disposal_fee = waste_disposal_fee_per_unit

    def optimize_product_discount(
        self,
        product: Product,
        current_stock: float,
        days_to_expiry: int,
        demand_profile: ProductDemandProfile,
        min_margin_pct: Optional[float] = None,
        waste_disposal_fee: Optional[float] = None,
    ) -> DiscountRecommendation:
        """Evaluate candidate discounts and select the optimal markdown recommendation.

        Parameters
        ----------
        product : Product
            Perishable product definition.
        current_stock : float
            Active unexpired inventory units available for sale.
        days_to_expiry : int
            Minimum days until expiration among available unexpired batches.
        demand_profile : ProductDemandProfile
            Estimated baseline demand (D0) and price sensitivity.
        min_margin_pct : Optional[float]
            Override for minimum gross margin percentage.
        waste_disposal_fee : Optional[float]
            Override for waste disposal cost per unit.

        Returns
        -------
        DiscountRecommendation
            Reconciled recommendation with detailed rationale and candidate audit.
        """
        active_margin_pct = self.default_min_margin_pct if min_margin_pct is None else min_margin_pct
        active_disposal_fee = self.waste_disposal_fee if waste_disposal_fee is None else waste_disposal_fee

        d0 = demand_profile.estimated_base_demand
        eta = demand_profile.estimated_price_sensitivity

        # Calculate minimum acceptable price based on margin floor
        min_price = compute_minimum_acceptable_price(product.unit_cost, active_margin_pct)

        # -------------------------------------------------------------------
        # Rule 1: Zero Stock Edge Case
        # -------------------------------------------------------------------
        if current_stock <= 1e-4:
            return DiscountRecommendation(
                product_id=product.product_id,
                product_name=product.name,
                category=product.category,
                historical_avg_daily_demand=d0,
                current_stock=0.0,
                days_to_expiry=days_to_expiry,
                recommended_discount_pct=0.0,
                recommended_selling_price=product.base_price,
                expected_units_sold=0.0,
                expected_units_wasted=0.0,
                expected_revenue=0.0,
                expected_gross_profit=0.0,
                expected_gross_margin_pct=0.0,
                minimum_margin_requirement_pct=active_margin_pct,
                minimum_acceptable_price=min_price,
                recommendation_explanation="No active inventory available; regular base price maintained.",
                sensitivity_source=demand_profile.sensitivity_source,
                price_sensitivity_used=eta,
                is_discounted=False,
                candidate_evaluations=[],
            )

        # -------------------------------------------------------------------
        # Rule 2: Unnecessary Discount Prevention
        # -------------------------------------------------------------------
        # If current stock is projected to sell out naturally before expiry
        # at full regular price (stock <= days_to_expiry * d0), expected waste at d=0 is 0.
        # Any discount here would unnecessarily sacrifice profit margin.
        total_full_price_capacity = max(1.0, float(days_to_expiry)) * d0
        if current_stock <= total_full_price_capacity:
            exp_sold = min(current_stock, d0)
            rev = round(exp_sold * product.base_price, 2)
            cogs = round(exp_sold * product.unit_cost, 2)
            gp = round(rev - cogs, 2)
            gm_pct = round((gp / rev) * 100.0, 2) if rev > 0 else 0.0

            cand_evals: List[CandidateEvaluation] = []
            for d in self.candidate_discounts:
                p_cand = round(product.base_price * (1.0 - d), 2)
                feasible = p_cand >= min_price - 1e-4
                cand_evals.append(
                    CandidateEvaluation(
                        discount_pct=round(d * 100.0, 1),
                        selling_price=p_cand,
                        is_feasible=feasible,
                        rejection_reason=None if feasible else f"Price ₹{p_cand:.2f} < Min ₹{min_price:.2f}",
                        expected_demand=d0,
                        expected_units_sold=exp_sold if d == 0 else min(current_stock, d0 * 1.2),
                        expected_units_wasted=0.0,
                        expected_revenue=rev,
                        expected_cogs=cogs,
                        expected_gross_profit=gp,
                        expected_gross_margin_pct=gm_pct,
                        net_objective_value=gp,
                    )
                )

            return DiscountRecommendation(
                product_id=product.product_id,
                product_name=product.name,
                category=product.category,
                historical_avg_daily_demand=d0,
                current_stock=round(current_stock, 1),
                days_to_expiry=days_to_expiry,
                recommended_discount_pct=0.0,
                recommended_selling_price=product.base_price,
                expected_units_sold=round(exp_sold, 1),
                expected_units_wasted=0.0,
                expected_revenue=rev,
                expected_gross_profit=gp,
                expected_gross_margin_pct=gm_pct,
                minimum_margin_requirement_pct=active_margin_pct,
                minimum_acceptable_price=min_price,
                recommendation_explanation=(
                    f"Stock ({current_stock:,.1f} units) is projected to sell out naturally before expiry "
                    f"at regular price ({total_full_price_capacity:,.1f} units demand capacity over {days_to_expiry}d); "
                    f"zero discount recommended to maximize gross margin."
                ),
                sensitivity_source=demand_profile.sensitivity_source,
                price_sensitivity_used=eta,
                is_discounted=False,
                candidate_evaluations=cand_evals,
            )

        # -------------------------------------------------------------------
        # Rule 3: Surplus Stock Clearance Optimization
        # -------------------------------------------------------------------
        candidate_evaluations: List[CandidateEvaluation] = []
        best_candidate: Optional[CandidateEvaluation] = None
        best_objective: float = -float("inf")

        for d in self.candidate_discounts:
            p_cand = round(product.base_price * (1.0 - d), 2)

            # Check Margin Floor Feasibility
            if p_cand < min_price - 1e-4:
                candidate_evaluations.append(
                    CandidateEvaluation(
                        discount_pct=round(d * 100.0, 1),
                        selling_price=p_cand,
                        is_feasible=False,
                        rejection_reason=f"Selling price ₹{p_cand:.2f} violates minimum margin price floor (₹{min_price:.2f})",
                        expected_demand=0.0,
                        expected_units_sold=0.0,
                        expected_units_wasted=0.0,
                        expected_revenue=0.0,
                        expected_cogs=0.0,
                        expected_gross_profit=0.0,
                        expected_gross_margin_pct=0.0,
                        net_objective_value=-float("inf"),
                    )
                )
                continue

            # Demand Estimation under Candidate Price
            exp_display_mult = 1.15 if d > 0.0 else (0.85 if days_to_expiry <= 2 else 1.0)
            exp_demand = max(0.0, round(d0 * (1.0 + eta * d) * exp_display_mult, 1))

            # Expected Sales & Physical Availability
            exp_sold = min(current_stock, exp_demand)
            rem_stock = max(0.0, current_stock - exp_sold)

            # Expected Waste Calculation
            if days_to_expiry <= 1:
                # Batches expire before tomorrow's opening
                exp_waste = rem_stock
            else:
                # Remaining stock has further days to sell at regular price
                future_demand_capacity = (days_to_expiry - 1) * d0
                exp_waste = max(0.0, rem_stock - future_demand_capacity)

            # Financials
            rev = round(exp_sold * p_cand, 2)
            cogs = round(exp_sold * product.unit_cost, 2)
            gp = round(rev - cogs, 2)
            gm_pct = round((gp / rev) * 100.0, 2) if rev > 0 else 0.0

            # Objective Function: Expected Gross Profit minus Waste Loss Penalty
            # Each wasted unit incurs direct loss of acquisition cost C plus disposal fee
            waste_penalty = exp_waste * (product.unit_cost + active_disposal_fee)
            net_obj = round(gp - waste_penalty, 2)

            eval_record = CandidateEvaluation(
                discount_pct=round(d * 100.0, 1),
                selling_price=p_cand,
                is_feasible=True,
                rejection_reason=None,
                expected_demand=exp_demand,
                expected_units_sold=round(exp_sold, 1),
                expected_units_wasted=round(exp_waste, 1),
                expected_revenue=rev,
                expected_cogs=cogs,
                expected_gross_profit=gp,
                expected_gross_margin_pct=gm_pct,
                net_objective_value=net_obj,
            )
            candidate_evaluations.append(eval_record)

            # Maximize Net Economic Objective
            # Tie-break preference: lower discount to preserve price integrity
            if net_obj > best_objective + 1e-4:
                best_objective = net_obj
                best_candidate = eval_record

        # Handle Case Where No Feasible Candidates Exist (Margin floor too high)
        if best_candidate is None:
            # Fall back to zero discount at base regular price
            base_p = product.base_price
            exp_sold = min(current_stock, d0)
            exp_waste = max(0.0, current_stock - (days_to_expiry * d0))
            rev = round(exp_sold * base_p, 2)
            cogs = round(exp_sold * product.unit_cost, 2)
            gp = round(rev - cogs, 2)
            gm_pct = round((gp / rev) * 100.0, 2) if rev > 0 else 0.0

            return DiscountRecommendation(
                product_id=product.product_id,
                product_name=product.name,
                category=product.category,
                historical_avg_daily_demand=d0,
                current_stock=round(current_stock, 1),
                days_to_expiry=days_to_expiry,
                recommended_discount_pct=0.0,
                recommended_selling_price=base_p,
                expected_units_sold=round(exp_sold, 1),
                expected_units_wasted=round(exp_waste, 1),
                expected_revenue=rev,
                expected_gross_profit=gp,
                expected_gross_margin_pct=gm_pct,
                minimum_margin_requirement_pct=active_margin_pct,
                minimum_acceptable_price=min_price,
                recommendation_explanation=(
                    f"Infeasible: Required minimum gross margin ({active_margin_pct:.1f}%) cannot be satisfied "
                    f"at any markdown discount (minimum price ₹{min_price:.2f} > base price ₹{base_p:.2f}); "
                    f"charging regular base price."
                ),
                sensitivity_source=demand_profile.sensitivity_source,
                price_sensitivity_used=eta,
                is_discounted=False,
                candidate_evaluations=candidate_evaluations,
            )

        # Build Explanation for Selected Recommendation
        opt_d = best_candidate.discount_pct / 100.0
        surplus = max(0.0, current_stock - total_full_price_capacity)
        if opt_d > 0.0:
            explanation = (
                f"Surplus stock at risk ({surplus:,.1f} units). Recommended {best_candidate.discount_pct:.0f}% clearance discount "
                f"at ₹{best_candidate.selling_price:.2f} balances gross profit (₹{best_candidate.expected_gross_profit:,.2f}) "
                f"and minimizes waste (expected waste: {best_candidate.expected_units_wasted:,.1f} units) while maintaining "
                f"{best_candidate.expected_gross_margin_pct:.1f}% gross margin (≥ {active_margin_pct:.1f}% floor)."
            )
        else:
            explanation = (
                f"Zero discount recommended. Even with surplus ({surplus:,.1f} units), full regular price ₹{product.base_price:.2f} "
                f"yields superior net economic value after accounting for margin retention."
            )

        return DiscountRecommendation(
            product_id=product.product_id,
            product_name=product.name,
            category=product.category,
            historical_avg_daily_demand=d0,
            current_stock=round(current_stock, 1),
            days_to_expiry=days_to_expiry,
            recommended_discount_pct=best_candidate.discount_pct,
            recommended_selling_price=best_candidate.selling_price,
            expected_units_sold=best_candidate.expected_units_sold,
            expected_units_wasted=best_candidate.expected_units_wasted,
            expected_revenue=best_candidate.expected_revenue,
            expected_gross_profit=best_candidate.expected_gross_profit,
            expected_gross_margin_pct=best_candidate.expected_gross_margin_pct,
            minimum_margin_requirement_pct=active_margin_pct,
            minimum_acceptable_price=min_price,
            recommendation_explanation=explanation,
            sensitivity_source=demand_profile.sensitivity_source,
            price_sensitivity_used=eta,
            is_discounted=opt_d > 0.0,
            candidate_evaluations=candidate_evaluations,
        )

    def optimize_all_products(
        self,
        products: List[Product],
        inventory_status: Dict[str, Tuple[float, int]],  # p_id -> (current_stock, days_to_expiry)
        demand_profiles: Dict[str, ProductDemandProfile],
        min_margin_pct: Optional[float] = None,
        waste_disposal_fee: Optional[float] = None,
    ) -> Dict[str, DiscountRecommendation]:
        """Generate recommendations for all products simultaneously."""
        recommendations: Dict[str, DiscountRecommendation] = {}
        for prod in products:
            p_id = prod.product_id
            stock, days_exp = inventory_status.get(p_id, (0.0, prod.shelf_life_days))
            profile = demand_profiles.get(
                p_id,
                ProductDemandProfile(
                    product_id=p_id,
                    product_name=prod.name,
                    category=prod.category,
                    estimated_base_demand=prod.avg_daily_demand,
                    estimated_price_sensitivity=prod.price_sensitivity,
                    sensitivity_source="configured_fallback",
                    historical_observations=0,
                    discount_variation_std=0.0,
                    unique_discount_levels=0,
                    mean_historical_price=prod.base_price,
                    mean_historical_discount_pct=0.0,
                    historical_waste_recorded=0.0,
                ),
            )
            recommendations[p_id] = self.optimize_product_discount(
                product=prod,
                current_stock=stock,
                days_to_expiry=days_exp,
                demand_profile=profile,
                min_margin_pct=min_margin_pct,
                waste_disposal_fee=waste_disposal_fee,
            )
        return recommendations


def recommendations_to_dataframe(
    recommendations: Dict[str, DiscountRecommendation],
    products: List[Product],
) -> pd.DataFrame:
    """Format dictionary of DiscountRecommendations into a 14-column presentation DataFrame.

    Columns match the official NEXAI Hackathon requirements:
    1. Product Name
    2. Category
    3. Current Stock
    4. Days to Expiry
    5. Base Price
    6. Recommended Discount (%)
    7. Recommended Selling Price
    8. Base Margin (%)
    9. Discounted Margin (%)
    10. Estimated Baseline Demand
    11. Price Sensitivity (Elasticity)
    12. Expected Waste Without Markdown
    13. Expected Waste With Markdown
    14. Recommendation Reason
    """
    prod_map = {p.product_id: p for p in products}
    rows: List[Dict[str, Any]] = []

    for p_id, rec in recommendations.items():
        prod = prod_map.get(p_id)
        if prod is None:
            continue

        base_margin_pct = round(((prod.base_price - prod.unit_cost) / prod.base_price) * 100.0, 2)
        disc_price = rec.recommended_selling_price
        disc_margin_pct = (
            round(((disc_price - prod.unit_cost) / disc_price) * 100.0, 2)
            if disc_price > 0
            else 0.0
        )
        exp_waste_no_md = round(
            max(0.0, rec.current_stock - max(1, rec.days_to_expiry) * rec.historical_avg_daily_demand), 1
        )

        rows.append(
            {
                "Product Name": rec.product_name,
                "Category": rec.category.title(),
                "Current Stock": rec.current_stock,
                "Days to Expiry": rec.days_to_expiry,
                "Base Price": prod.base_price,
                "Recommended Discount (%)": rec.recommended_discount_pct,
                "Recommended Selling Price": rec.recommended_selling_price,
                "Base Margin (%)": base_margin_pct,
                "Discounted Margin (%)": disc_margin_pct,
                "Estimated Baseline Demand": round(rec.historical_avg_daily_demand, 1),
                "Price Sensitivity (Elasticity)": round(rec.price_sensitivity_used, 2),
                "Expected Waste Without Markdown": exp_waste_no_md,
                "Expected Waste With Markdown": rec.expected_units_wasted,
                "Recommendation Reason": rec.recommendation_explanation,
            }
        )

    return pd.DataFrame(rows)

