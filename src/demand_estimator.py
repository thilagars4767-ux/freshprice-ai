"""FreshPrice AI — Product-Specific Demand and Sensitivity Estimator.

NEXAI 2026 Hackathon (PS 4.1: Track 4 Grocery Retail).

This module estimates product-level baseline demand velocity (D0) and price
sensitivity (elasticity) from synthetic historical transaction records.

Data Leakage Prevention:
Estimations strictly accept an `as_of_date` or `cutoff_date`. A simulation-day
recommendation only utilizes historical records up to that cutoff, ensuring
future sales are never leaked to inform earlier pricing decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import sys
from typing import Dict, List, Optional, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from src.demand_history import DEFAULT_HISTORICAL_FILE
from src.store_simulator import DEFAULT_PRODUCTS, Product


@dataclass(frozen=True)
class ProductDemandProfile:
    """Estimated demand parameters for a single product."""
    product_id: str
    product_name: str
    category: str
    estimated_base_demand: float
    estimated_price_sensitivity: float
    sensitivity_source: str  # "historical_estimate" or "configured_fallback"
    historical_observations: int
    discount_variation_std: float
    unique_discount_levels: int
    mean_historical_price: float
    mean_historical_discount_pct: float
    historical_waste_recorded: float


class DemandEstimator:
    """Estimates baseline demand and price responsiveness from historical data without leakage."""

    def __init__(
        self,
        historical_df: Optional[pd.DataFrame] = None,
        historical_file: Optional[Union[Path, str]] = None,
        products: Optional[List[Product]] = None,
        min_discount_std: float = 2.0,
        min_unique_discounts: int = 2,
    ) -> None:
        """Initialize the DemandEstimator.

        Parameters
        ----------
        historical_df : Optional[pd.DataFrame]
            In-memory DataFrame of historical demand records.
        historical_file : Optional[Union[Path, str]]
            Path to historical CSV file if DataFrame not provided.
        products : Optional[List[Product]]
            Catalog of products for metadata and fallback sensitivities.
        min_discount_std : float
            Minimum standard deviation in discount percentage required to run regression.
        min_unique_discounts : int
            Minimum number of distinct discount levels required to estimate sensitivity.
        """
        self.products = products or list(DEFAULT_PRODUCTS)
        self.products_map = {p.product_id: p for p in self.products}
        self.min_discount_std = min_discount_std
        self.min_unique_discounts = min_unique_discounts

        if historical_df is not None:
            self._df = historical_df.copy()
        else:
            file_path = Path(historical_file or DEFAULT_HISTORICAL_FILE)
            if file_path.exists():
                self._df = pd.read_csv(file_path)
            else:
                self._df = pd.DataFrame()

    def get_historical_data(self, cutoff_date: Optional[Union[str, date]] = None) -> pd.DataFrame:
        """Return historical DataFrame filtered up to cutoff_date (inclusive) to prevent data leakage."""
        if self._df.empty:
            return pd.DataFrame()

        df = self._df.copy()
        if cutoff_date is not None:
            cutoff_str = cutoff_date.isoformat() if isinstance(cutoff_date, date) else str(cutoff_date)
            df = df[df["date"] <= cutoff_str]
        return df

    def estimate_product_profile(
        self,
        product: Product,
        cutoff_date: Optional[Union[str, date]] = None,
    ) -> ProductDemandProfile:
        """Estimate baseline demand and price response for a product up to cutoff_date.

        Parameters
        ----------
        product : Product
            Catalog item to profile.
        cutoff_date : Optional[Union[str, date]]
            Strict temporal boundary preventing future data leakage.

        Returns
        -------
        ProductDemandProfile
            Reconciled demand profile with sensitivity and fallback origin.
        """
        hist_df = self.get_historical_data(cutoff_date=cutoff_date)
        p_id = product.product_id

        if hist_df.empty or p_id not in hist_df["product_id"].values:
            # Fallback when no historical records exist
            return ProductDemandProfile(
                product_id=p_id,
                product_name=product.name,
                category=product.category,
                estimated_base_demand=product.avg_daily_demand,
                estimated_price_sensitivity=product.price_sensitivity,
                sensitivity_source="configured_fallback",
                historical_observations=0,
                discount_variation_std=0.0,
                unique_discount_levels=0,
                mean_historical_price=product.base_price,
                mean_historical_discount_pct=0.0,
                historical_waste_recorded=0.0,
            )

        p_df = hist_df[hist_df["product_id"] == p_id].sort_values("date")
        n_obs = len(p_df)

        # Baseline Demand Estimation (average sales on un-discounted days or mean sales)
        zero_disc_df = p_df[p_df["discount_pct"] <= 1e-4]
        if not zero_disc_df.empty:
            base_d_est = float(zero_disc_df["units_sold"].mean())
        else:
            base_d_est = float(p_df["units_sold"].mean())

        base_d_est = max(1.0, round(base_d_est, 1))

        # Check Price and Discount Variation
        disc_std = float(p_df["discount_pct"].std()) if n_obs > 1 else 0.0
        unique_discs = int(p_df["discount_pct"].nunique())

        mean_price = float(p_df["price"].mean())
        mean_disc = float(p_df["discount_pct"].mean())
        tot_waste = float(p_df["units_wasted"].sum())

        # Econometric Qualification Check
        # If standard deviation of discounts is too low, or too few distinct discounts exist,
        # statistical estimation of price elasticity is unreliable -> use configured fallback.
        if disc_std < self.min_discount_std or unique_discs < self.min_unique_discounts:
            return ProductDemandProfile(
                product_id=p_id,
                product_name=product.name,
                category=product.category,
                estimated_base_demand=base_d_est,
                estimated_price_sensitivity=product.price_sensitivity,
                sensitivity_source="configured_fallback",
                historical_observations=n_obs,
                discount_variation_std=round(disc_std, 2),
                unique_discount_levels=unique_discs,
                mean_historical_price=round(mean_price, 2),
                mean_historical_discount_pct=round(mean_disc, 2),
                historical_waste_recorded=round(tot_waste, 1),
            )

        # OLS Estimation of Price Sensitivity:
        # Sales Response: Q_t = D0 * (1 + eta * discount_frac_t)
        # Delta Q / D0 = eta * discount_frac
        x = (p_df["discount_pct"] / 100.0).to_numpy()
        y = p_df["units_sold"].to_numpy()

        cov_xy = np.cov(x, y)[0, 1] if len(x) > 1 else 0.0
        var_x = np.var(x)

        if var_x > 1e-6:
            slope = cov_xy / var_x
            est_eta = slope / base_d_est
        else:
            est_eta = 0.0

        # Sanity Check on Estimated Elasticity:
        # Real-world grocery elasticity for perishable staples is positive (Q rises with discount)
        # and typically within [0.2, 5.0]. If noisy historical data produces negative slope
        # or extreme values, fall back safely to configured domain baseline.
        if 0.20 <= est_eta <= 5.0:
            final_eta = round(float(est_eta), 2)
            source = "historical_estimate"
        else:
            final_eta = product.price_sensitivity
            source = "configured_fallback"

        return ProductDemandProfile(
            product_id=p_id,
            product_name=product.name,
            category=product.category,
            estimated_base_demand=base_d_est,
            estimated_price_sensitivity=final_eta,
            sensitivity_source=source,
            historical_observations=n_obs,
            discount_variation_std=round(disc_std, 2),
            unique_discount_levels=unique_discs,
            mean_historical_price=round(mean_price, 2),
            mean_historical_discount_pct=round(mean_disc, 2),
            historical_waste_recorded=round(tot_waste, 1),
        )

    def estimate_all_profiles(
        self, cutoff_date: Optional[Union[str, date]] = None
    ) -> Dict[str, ProductDemandProfile]:
        """Estimate profiles for all products in the catalog without data leakage."""
        profiles: Dict[str, ProductDemandProfile] = {}
        for prod in self.products:
            profiles[prod.product_id] = self.estimate_product_profile(prod, cutoff_date=cutoff_date)
        return profiles

    def estimate_all_products(
        self, products: Optional[List[Product]] = None, cutoff_date: Optional[Union[str, date]] = None
    ) -> Dict[str, ProductDemandProfile]:
        """Alias for estimate_all_profiles accepting an optional product list."""
        target_prods = products if products is not None else self.products
        profiles: Dict[str, ProductDemandProfile] = {}
        for prod in target_prods:
            profiles[prod.product_id] = self.estimate_product_profile(prod, cutoff_date=cutoff_date)
        return profiles
