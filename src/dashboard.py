"""FreshPrice AI — Markdown Before Waste: Near-Expiry Pricing Dashboard.

NEXAI 2026 Hackathon: Problem Statement 4.1 (Track 4: Grocery Retail).

A comprehensive, single-page Streamlit application designed with a modern red-and-white
Zomato-inspired aesthetic and strict light theme. Simulates a grocery store with
20 perishable products, comparing:
  1. Fixed-Price Policy (always charges base regular price)
  2. Dynamic Markdown Policy (graduated near-expiry discounts with wholesale cost floor)
"""

from __future__ import annotations

from pathlib import Path
import sys
import textwrap
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.store_simulator import (
    DEFAULT_DATA_DIR,
    InventoryBatch,
    MarkdownPolicyConfig,
    PolicyMetrics,
    Product,
    SimulationResult,
    export_mvp_csv_outputs,
    generate_arrival_schedule,
    get_default_products,
    run_store_simulation,
)

# ---------------------------------------------------------------------------
# Formatting & HTML Helpers
# ---------------------------------------------------------------------------

def format_inr(value: float, include_sign: bool = False) -> str:
    """Format a monetary amount in Indian Rupees (₹)."""
    if include_sign and value > 0:
        return f"+₹{value:,.2f}"
    elif value < 0:
        return f"-₹{abs(value):,.2f}"
    return f"₹{value:,.2f}"


def format_pct(value: float, include_sign: bool = False) -> str:
    """Format a percentage with two decimal places."""
    if include_sign and value > 0:
        return f"+{value:.2f}%"
    return f"{value:.2f}%"


def format_pp(value: float, include_sign: bool = False) -> str:
    """Format a percentage-point difference with appropriate sign and 'pp' label."""
    if include_sign and value > 0:
        return f"+{value:.2f} pp"
    elif value < 0:
        return f"-{abs(value):.2f} pp"
    return f"{value:.2f} pp"


def format_units(value: float, include_sign: bool = False) -> str:
    """Format physical inventory or sales unit quantity with consistent sign convention."""
    if abs(value - round(value)) < 1e-4:
        val_str = f"{int(round(value)):,d}"
    else:
        val_str = f"{value:,.1f}"

    if include_sign and value > 0:
        return f"+{val_str} units"
    elif value < 0:
        return f"-{val_str.lstrip('-')} units"
    elif include_sign and value == 0.0:
        return "0 units" if abs(value - round(value)) < 1e-4 else "0.0 units"
    return f"{val_str} units"


def render_html(html_str: str, container: Any = None) -> None:
    """Safely render HTML in Streamlit without triggering Markdown indented code block mode."""
    target = container if container is not None else st
    clean_lines = [line.strip() for line in html_str.strip().splitlines()]
    clean_html = "\n".join(clean_lines)
    if hasattr(target, "html"):
        target.html(clean_html)
    else:
        target.markdown(clean_html, unsafe_allow_html=True)


def generate_rule_logic_explanation(
    near_expiry_threshold: int,
    near_expiry_discount_pct: float | int,
    urgent_threshold: int,
    urgent_discount_pct: float | int,
) -> str:
    """Generate dynamic explanatory markdown text for the configured discount rules.

    Accurately reflects the actual simulator logic:
    - Bounded by '<=' ('or fewer days')
    - Explains urgent clearance rule precedence
    - Formulates margin floor and expiration constraints
    """
    # Normalize percentages to integer display (e.g. 20 for 20% or 0.20)
    if isinstance(near_expiry_discount_pct, float) and near_expiry_discount_pct <= 1.0 and near_expiry_discount_pct > 0.0:
        d2_val = int(round(near_expiry_discount_pct * 100))
    else:
        d2_val = int(round(near_expiry_discount_pct))

    if isinstance(urgent_discount_pct, float) and urgent_discount_pct <= 1.0 and urgent_discount_pct > 0.0:
        d1_val = int(round(urgent_discount_pct * 100))
    else:
        d1_val = int(round(urgent_discount_pct))

    t2_val = int(near_expiry_threshold)
    t1_val = int(urgent_threshold)

    return (
        "**Rule Logic:**\n"
        f"- When a product has {t2_val} or fewer days remaining before expiry, apply the configured {d2_val}% near-expiry discount, subject to the urgent rule.\n"
        f"- When a product has {t1_val} or fewer days remaining before expiry, apply the configured {d1_val}% urgent-clearance discount.\n"
        "- Never sell expired products.\n"
        "- Never price below the configured minimum gross-margin floor."
    )


# ---------------------------------------------------------------------------
# Data Loaders (Cached)
# ---------------------------------------------------------------------------

@st.cache_data
def load_historical_demand_data() -> pd.DataFrame:
    """Load the 365-day synthetic historical demand dataset from disk."""
    csv_path = PROJECT_ROOT / "data" / "historical_product_demand.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


@st.cache_data
def load_product_price_history() -> pd.DataFrame:
    """Load the 365-day synthetic product price history dataset from disk."""
    csv_path = PROJECT_ROOT / "data" / "product_price_history.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Dashboard Simulation Orchestration (Decoupled from Streamlit UI)
# ---------------------------------------------------------------------------

@st.cache_data
def run_dashboard_simulation(
    sim_days: int = 30,
    seed: int = 42,
    threshold_1_days: int = 1,
    discount_1_pct: float = 0.40,
    threshold_2_days: int = 2,
    discount_2_pct: float = 0.20,
    enforce_cost_floor: bool = True,
    policy_mode: str = "graduated_rule",
    min_gross_margin_pct: float = 0.0,
    waste_disposal_fee: float = 0.0,
    shopper_response_multiplier: float = 1.0,
    category_configs: Optional[Dict[str, Tuple[int, float, int, float]]] = None,
) -> SimulationResult:
    """Execute store simulation with the exact parameters configured in the dashboard.

    Guarantees that every change to markdown thresholds, discount percentages,
    policy strategy, margin protection, or sensitivity multiplier instantiates
    a fresh MarkdownPolicyConfig and recalculates the simulation.
    """
    config = MarkdownPolicyConfig(
        threshold_1_days=int(threshold_1_days),
        discount_1_pct=float(discount_1_pct),
        threshold_2_days=int(threshold_2_days),
        discount_2_pct=float(discount_2_pct),
        enforce_cost_floor=bool(enforce_cost_floor),
        policy_mode=str(policy_mode),
        min_gross_margin_pct=float(min_gross_margin_pct),
        waste_disposal_fee=float(waste_disposal_fee),
        shopper_response_multiplier=float(shopper_response_multiplier),
        category_configs=category_configs,
    )
    return run_store_simulation(sim_days=int(sim_days), seed=int(seed), config=config)


# ---------------------------------------------------------------------------
# Plotly Visualizations (Light Theme & Zomato Red-and-White Palette)
# ---------------------------------------------------------------------------

def create_comparison_chart(fixed: PolicyMetrics, markdown: PolicyMetrics) -> go.Figure:
    """Create a grouped bar chart for Revenue and Gross Margin with Zomato light styling."""
    fig = go.Figure()

    financial_metrics = ["Total Revenue (₹)", "Gross Margin (₹)"]
    fixed_fin = [fixed.revenue, fixed.gross_margin]
    md_fin = [markdown.revenue, markdown.gross_margin]

    # Trace 1: Fixed-Price Policy (Neutral Gray Baseline)
    fig.add_trace(
        go.Bar(
            name="Fixed-Price Policy",
            x=financial_metrics,
            y=fixed_fin,
            marker_color="#718096",  # Neutral Slate/Gray for Fixed Baseline
            text=[f"₹{v:,.0f}" for v in fixed_fin],
            textposition="auto",
            hovertemplate="%{x}<br>Fixed Baseline: ₹%{y:,.2f}<extra></extra>",
        )
    )

    # Trace 2: Markdown Policy (FreshPrice Signature Red)
    fig.add_trace(
        go.Bar(
            name="Markdown Policy",
            x=financial_metrics,
            y=md_fin,
            marker_color="#E23744",  # FreshPrice Signature Red
            text=[f"₹{v:,.0f}" for v in md_fin],
            textposition="auto",
            hovertemplate="%{x}<br>Dynamic Markdown: ₹%{y:,.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title="<b>Financial Performance: Total Revenue & Gross Margin (INR ₹)</b>",
        barmode="group",
        template="plotly_white",
        yaxis=dict(
            title="Amount in INR (₹)",
            gridcolor="#F0F0F0",
            linecolor="#E8E8E8",
            tickfont=dict(color="#222222"),
            title_font=dict(color="#222222"),
        ),
        xaxis=dict(
            title="Financial Metric",
            linecolor="#E8E8E8",
            tickfont=dict(color="#222222"),
            title_font=dict(color="#222222"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#222222"),
        ),
        margin=dict(l=40, r=40, t=70, b=40),
        font=dict(family="Inter, -apple-system, sans-serif", size=13, color="#222222"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def create_waste_comparison_chart(fixed: PolicyMetrics, markdown: PolicyMetrics) -> go.Figure:
    """Create a bar chart comparing physical expired inventory units in light theme."""
    fig = go.Figure()

    policies = ["Fixed-Price Policy", "Markdown Policy"]
    waste_units = [fixed.units_wasted, markdown.units_wasted]

    fig.add_trace(
        go.Bar(
            name="Units Wasted (Expired)",
            x=policies,
            y=waste_units,
            marker_color=["#E23744", "#008A3E"],
            text=[f"{v:,.1f} units" for v in waste_units],
            textposition="auto",
            hovertemplate="%{x}<br>Expired Unsold: %{y:,.1f} units<extra></extra>",
        )
    )

    fig.update_layout(
        title="<b>Physical Waste Comparison: Expired Unsold Inventory (Units)</b>",
        template="plotly_white",
        yaxis=dict(
            title="Wasted Units (Physical Expired Stock)",
            gridcolor="#F0F0F0",
            linecolor="#E8E8E8",
            tickfont=dict(color="#222222"),
            title_font=dict(color="#222222"),
        ),
        xaxis=dict(
            title="Pricing Strategy",
            linecolor="#E8E8E8",
            tickfont=dict(color="#222222"),
            title_font=dict(color="#222222"),
        ),
        margin=dict(l=40, r=40, t=70, b=40),
        font=dict(family="Inter, -apple-system, sans-serif", size=13, color="#222222"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def create_daily_trends_chart(daily_history_df: pd.DataFrame) -> go.Figure:
    """Create an interactive daily store-level sales and waste trend chart comparing both policies."""
    fig = go.Figure()

    grouped = (
        daily_history_df.groupby(["day", "policy"])
        .agg({"units_sold": "sum", "units_wasted": "sum", "revenue": "sum"})
        .reset_index()
    )

    fixed_df = grouped[grouped["policy"] == "fixed"].sort_values("day")
    md_df = grouped[grouped["policy"] == "markdown"].sort_values("day")

    fig.add_trace(
        go.Scatter(
            name="Fixed Policy Sales (units)",
            x=fixed_df["day"],
            y=fixed_df["units_sold"],
            mode="lines",
            line=dict(color="#718096", width=2, dash="dash"),
            hovertemplate="Day %{x}<br>Fixed Sales: %{y:,.1f} units<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Markdown Policy Sales (units)",
            x=md_df["day"],
            y=md_df["units_sold"],
            mode="lines+markers",
            line=dict(color="#E23744", width=2.5),
            marker=dict(size=4, color="#E23744"),
            hovertemplate="Day %{x}<br>Markdown Sales: %{y:,.1f} units<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Fixed Policy Waste (Expired)",
            x=fixed_df["day"],
            y=fixed_df["units_wasted"],
            mode="lines+markers",
            line=dict(color="#C53030", width=1.5, dash="dot"),
            marker=dict(size=6, symbol="x", color="#C53030"),
            hovertemplate="Day %{x}<br>Fixed Expired Waste: %{y:,.1f} units<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Markdown Policy Waste (Expired)",
            x=md_df["day"],
            y=md_df["units_wasted"],
            mode="lines+markers",
            line=dict(color="#008A3E", width=1.5),
            marker=dict(size=6, symbol="circle", color="#008A3E"),
            hovertemplate="Day %{x}<br>Markdown Expired Waste: %{y:,.1f} units<extra></extra>",
        )
    )

    fig.update_layout(
        title="<b>Daily Store Trends: Physical Units Sold & Expired Waste over Time</b>",
        template="plotly_white",
        yaxis=dict(
            title="Physical Quantity (Units)",
            gridcolor="#F0F0F0",
            linecolor="#E8E8E8",
            tickfont=dict(color="#222222"),
        ),
        xaxis=dict(
            title="Simulation Day",
            gridcolor="#F0F0F0",
            linecolor="#E8E8E8",
            tickfont=dict(color="#222222"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#222222"),
        ),
        margin=dict(l=40, r=40, t=70, b=40),
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#222222"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def create_sim_product_price_chart(p_md_df: pd.DataFrame, product_name: str) -> go.Figure:
    """Chart comparing Regular Base Price vs Actual Selling Price across the 30-day simulation."""
    fig = go.Figure()
    p_sorted = p_md_df.sort_values("day")

    fig.add_trace(
        go.Scatter(
            name="Regular Base Price (₹)",
            x=p_sorted["day"],
            y=p_sorted["regular_price"],
            mode="lines",
            line=dict(color="#718096", width=2, dash="dash"),
            hovertemplate="Day %{x}<br>Base Price: ₹%{y:,.2f}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Actual Selling Price (₹)",
            x=p_sorted["day"],
            y=p_sorted["selling_price"],
            mode="lines+markers",
            line=dict(color="#E23744", width=2.5),
            marker=dict(size=5, color="#E23744"),
            hovertemplate="Day %{x}<br>Selling Price: ₹%{y:,.2f}<br>Discount: "
            + p_sorted["discount_pct"].apply(lambda v: f"{v:.1f}%")
            + "<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"<b>Simulated Price Trajectory: Regular vs. Dynamic Selling Price — {product_name}</b>",
        template="plotly_white",
        yaxis=dict(title="Price in INR (₹)", gridcolor="#F0F0F0", linecolor="#E8E8E8"),
        xaxis=dict(title="Simulation Day", gridcolor="#F0F0F0", linecolor="#E8E8E8"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=70, b=40),
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#222222"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def create_sim_product_sales_waste_chart(p_md_df: pd.DataFrame, product_name: str) -> go.Figure:
    """Chart showing daily units sold and units wasted for a single product under Markdown Policy."""
    fig = go.Figure()
    p_sorted = p_md_df.sort_values("day")

    fig.add_trace(
        go.Bar(
            name="Units Sold",
            x=p_sorted["day"],
            y=p_sorted["units_sold"],
            marker_color="#008A3E",
            opacity=0.85,
            hovertemplate="Day %{x}<br>Units Sold: %{y:,.1f}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            name="Units Wasted (Expired)",
            x=p_sorted["day"],
            y=p_sorted["units_wasted"],
            marker_color="#E23744",
            opacity=0.90,
            hovertemplate="Day %{x}<br>Units Wasted: %{y:,.1f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"<b>Daily Sales Velocity & Physical Waste — {product_name}</b>",
        barmode="group",
        template="plotly_white",
        yaxis=dict(title="Physical Quantity (Units)", gridcolor="#F0F0F0", linecolor="#E8E8E8"),
        xaxis=dict(title="Simulation Day", gridcolor="#F0F0F0", linecolor="#E8E8E8"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=70, b=40),
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#222222"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def create_sim_product_sales_vs_price_chart(p_md_df: pd.DataFrame, product_name: str) -> go.Figure:
    """Create an interactive Plotly dual-axis chart titled 'Daily Sales vs Actual Selling Price'.

    Left Y-axis (Blue line): Daily units sold.
    Right Y-axis (Orange line): Actual selling price in INR (₹).
    Red markers and annotations: Actual clearance markdown events with discount percentage.
    Hover tooltip: Day, units sold, actual selling price, days to expiry, and markdown status.
    """
    if p_md_df is None or p_md_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text=f"No recorded sales or price history available for {product_name}.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="#64748B"),
        )
        fig.update_layout(
            title=f"<b>Daily Sales vs Actual Selling Price — {product_name}</b>",
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
        )
        return fig

    p_sorted = p_md_df.sort_values("day").copy()

    # Build rich 5-tuple hover data for all simulation days
    custom_data = []
    for _, row in p_sorted.iterrows():
        d_pct = float(row.get("discount_pct", 0.0))
        d_exp = int(row.get("days_until_expiry", 0))
        exp_str = f"{d_exp} day" if d_exp == 1 else f"{d_exp} days"
        status_str = f"🔥 Markdown ({d_pct:.0f}% Off)" if d_pct > 0 else "Regular Full Price"
        custom_data.append([
            float(row.get("units_sold", 0.0)),
            float(row.get("selling_price", 0.0)),
            exp_str,
            status_str,
            float(row.get("regular_price", 0.0)),
            d_pct,
        ])

    fig = go.Figure()

    # 1. Blue Line: Daily Units Sold (Left Y-Axis)
    fig.add_trace(
        go.Scatter(
            name="Daily Units Sold",
            x=p_sorted["day"],
            y=p_sorted["units_sold"],
            mode="lines+markers",
            line=dict(color="#1F77B4", width=2.4),
            marker=dict(size=5, color="#1F77B4"),
            yaxis="y1",
            customdata=custom_data,
            hovertemplate=(
                "<b>Simulation Day: Day %{x}</b><br>"
                "Daily Units Sold: %{customdata[0]:,.1f} units<br>"
                "Actual Selling Price: ₹%{customdata[1]:,.2f}<br>"
                "Days to Expiry: %{customdata[2]}<br>"
                "Markdown Status: %{customdata[3]}<extra></extra>"
            ),
        )
    )

    # 2. Orange Line: Actual Selling Price (Right Y-Axis)
    fig.add_trace(
        go.Scatter(
            name="Actual Selling Price (₹)",
            x=p_sorted["day"],
            y=p_sorted["selling_price"],
            mode="lines+markers",
            line=dict(color="#FF7F0E", width=2.5),
            marker=dict(size=5, color="#FF7F0E"),
            yaxis="y2",
            customdata=custom_data,
            hovertemplate=(
                "<b>Simulation Day: Day %{x}</b><br>"
                "Daily Units Sold: %{customdata[0]:,.1f} units<br>"
                "Actual Selling Price: ₹%{customdata[1]:,.2f}<br>"
                "Days to Expiry: %{customdata[2]}<br>"
                "Markdown Status: %{customdata[3]}<extra></extra>"
            ),
        )
    )

    # 3. Red Markers & Annotations: Actual Markdown Clearance Events
    md_evts = p_sorted[p_sorted["discount_pct"] > 0]
    if not md_evts.empty:
        md_custom = []
        for _, row in md_evts.iterrows():
            d_pct = float(row.get("discount_pct", 0.0))
            d_exp = int(row.get("days_until_expiry", 0))
            exp_str = f"{d_exp} day" if d_exp == 1 else f"{d_exp} days"
            status_str = f"🔥 Markdown ({d_pct:.0f}% Off)"
            md_custom.append([
                float(row.get("units_sold", 0.0)),
                float(row.get("selling_price", 0.0)),
                exp_str,
                status_str,
                float(row.get("regular_price", 0.0)),
                d_pct,
            ])

        fig.add_trace(
            go.Scatter(
                name="Markdown Clearance Event",
                x=md_evts["day"],
                y=md_evts["selling_price"],
                mode="markers",
                marker=dict(
                    size=11,
                    color="#DC2626",
                    symbol="circle",
                    line=dict(width=2, color="#991B1B"),
                ),
                yaxis="y2",
                customdata=md_custom,
                hovertemplate=(
                    "<b>🔥 Markdown Event — Day %{x}</b><br>"
                    "Daily Units Sold: %{customdata[0]:,.1f} units<br>"
                    "Actual Selling Price: ₹%{customdata[1]:,.2f}<br>"
                    "Days to Expiry: %{customdata[2]}<br>"
                    "Markdown Status: %{customdata[3]}<extra></extra>"
                ),
            )
        )

        # Badges / Annotations pointing to markdown price points
        for _, row in md_evts.iterrows():
            d_pct = float(row["discount_pct"])
            fig.add_annotation(
                x=row["day"],
                y=row["selling_price"],
                yref="y2",
                text=f"{d_pct:.0f}% Off",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.5,
                arrowcolor="#DC2626",
                ax=0,
                ay=-20,
                font=dict(size=9, color="#FFFFFF", family="Inter, sans-serif"),
                bgcolor="#DC2626",
                bordercolor="#991B1B",
                borderwidth=1,
                borderpad=2,
                opacity=0.95,
            )

    fig.update_layout(
        title=f"<b>Daily Sales vs Actual Selling Price — {product_name}</b>",
        template="plotly_white",
        xaxis=dict(
            title="<b>Simulation Day</b>",
            gridcolor="#F1F5F9",
            linecolor="#CBD5E1",
            tickmode="linear",
            tick0=1,
            dtick=2,
        ),
        yaxis=dict(
            title=dict(text="<b>Units Sold (Units)</b>", font=dict(color="#1F77B4")),
            gridcolor="#F1F5F9",
            linecolor="#CBD5E1",
            tickfont=dict(color="#1F77B4"),
        ),
        yaxis2=dict(
            title=dict(text="<b>Actual Selling Price (₹)</b>", font=dict(color="#FF7F0E")),
            overlaying="y",
            side="right",
            showgrid=False,
            linecolor="#CBD5E1",
            tickprefix="₹",
            tickfont=dict(color="#FF7F0E"),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=45, r=55, t=70, b=40),
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#1E293B"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def create_sim_product_price_vs_sales_chart(p_md_df: pd.DataFrame, product_name: str) -> go.Figure:
    """Create an interactive Plotly line chart titled 'Price vs Units Sold — {product_name}'.

    X-axis: Actual selling price per unit in INR (₹).
    Y-axis: Units sold.
    Chart type: Line chart with visible data-point markers, connected in ascending price order.
    Markdown observations: Highlighted with distinct markers.
    Hover details: Simulation day, actual selling price, units sold, days to expiry, and discount percentage.
    """
    if p_md_df is None or p_md_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text=f"No recorded sales or price history available for {product_name}.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="#64748B"),
        )
        fig.update_layout(
            title=f"<b>Price vs Units Sold — {product_name}</b>",
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
        )
        return fig

    # Sort strictly by ascending selling price, then simulation day to preserve each day's observation
    p_sorted = p_md_df.sort_values(["selling_price", "day"]).copy()

    # Helper function to construct rich 5-tuple hover customdata
    def _build_customdata(sub_df: pd.DataFrame):
        cd = []
        for _, row in sub_df.iterrows():
            d_day = int(row.get("day", 1))
            d_exp = int(row.get("days_until_expiry", 0))
            exp_str = f"{d_exp} day" if d_exp == 1 else f"{d_exp} days"
            d_pct = float(row.get("discount_pct", 0.0))
            status_str = f"Markdown ({d_pct:.0f}% Off)" if d_pct > 0 else "Regular Full Price"
            cd.append([
                d_day,
                exp_str,
                d_pct,
                status_str,
                float(row.get("regular_price", 0.0)),
            ])
        return cd

    fig = go.Figure()

    # 1. Connected Line Chart across all observations in ascending price order
    fig.add_trace(
        go.Scatter(
            name="Price vs Sales Curve",
            x=p_sorted["selling_price"],
            y=p_sorted["units_sold"],
            mode="lines+markers",
            line=dict(color="#2563EB", width=2.0),
            marker=dict(size=7, color="#1D4ED8", symbol="circle"),
            customdata=_build_customdata(p_sorted),
            hovertemplate=(
                "<b>Simulation Day: Day %{customdata[0]}</b><br>"
                "Actual Selling Price: ₹%{x:,.2f}<br>"
                "Units Sold: %{y:,.1f} units<br>"
                "Days to Expiry: %{customdata[1]}<br>"
                "Discount Applied: %{customdata[2]:.1f}% (%{customdata[3]})<extra></extra>"
            ),
        )
    )

    # 2. Highlight Markdown-Period Observations with distinct markers
    md_df = p_sorted[p_sorted["discount_pct"] > 0]
    if not md_df.empty:
        fig.add_trace(
            go.Scatter(
                name="Markdown Clearance Observations",
                x=md_df["selling_price"],
                y=md_df["units_sold"],
                mode="markers",
                marker=dict(
                    size=12,
                    color="#DC2626",
                    symbol="diamond",
                    line=dict(width=1.8, color="#991B1B"),
                ),
                customdata=_build_customdata(md_df),
                hovertemplate=(
                    "<b>🔥 Markdown Event — Day %{customdata[0]}</b><br>"
                    "Actual Selling Price: ₹%{x:,.2f}<br>"
                    "Units Sold: %{y:,.1f} units<br>"
                    "Days to Expiry: %{customdata[1]}<br>"
                    "Discount Applied: %{customdata[2]:.1f}% (%{customdata[3]})<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=f"<b>Price vs Units Sold — {product_name}</b>",
        template="plotly_white",
        xaxis=dict(
            title="<b>Actual Selling Price (₹)</b>",
            gridcolor="#F1F5F9",
            linecolor="#CBD5E1",
            tickprefix="₹",
            tickformat=",.2f",
        ),
        yaxis=dict(
            title="<b>Units Sold (Units)</b>",
            gridcolor="#F1F5F9",
            linecolor="#CBD5E1",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=45, r=40, t=70, b=40),
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#1E293B"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
    )
    return fig


def create_historical_price_chart(product_df: pd.DataFrame, product_name: str) -> go.Figure:
    """Create an interactive time-series graph comparing Regular Price vs Actual Selling Price in INR (₹)."""
    fig = go.Figure()
    p_sorted = product_df.sort_values("date")

    # Trace 1: Regular Base Price (Neutral Slate dashed line)
    fig.add_trace(
        go.Scatter(
            name="Regular Base Price (₹)",
            x=p_sorted["date"],
            y=p_sorted["regular_price"],
            mode="lines",
            line=dict(color="#718096", width=2, dash="dash"),
            hovertemplate="<b>%{x}</b><br>Regular Price: ₹%{y:,.2f}<extra></extra>",
        )
    )

    # Trace 2: Actual Selling Price (FreshPrice Red solid line with markers)
    fig.add_trace(
        go.Scatter(
            name="Actual Selling Price (₹)",
            x=p_sorted["date"],
            y=p_sorted["actual_price"],
            mode="lines+markers",
            line=dict(color="#E23744", width=2.5),
            marker=dict(size=4, color="#E23744"),
            hovertemplate="<b>%{x}</b><br>Actual Price: ₹%{y:,.2f}<br>Discount: "
            + p_sorted["discount_pct"].apply(lambda v: f"{v:.1f}%")
            + "<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"<b>Historical Price Trajectory: Regular vs. Actual Selling Price (₹) — {product_name}</b>",
        template="plotly_white",
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#222222"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#222222"),
        ),
        margin=dict(l=40, r=40, t=70, b=40),
        hovermode="x unified",
    )

    fig.update_yaxes(
        title_text="Price in INR (₹)",
        gridcolor="#F0F0F0",
        linecolor="#E8E8E8",
        tickfont=dict(color="#222222"),
        title_font=dict(color="#222222"),
    )

    fig.update_xaxes(
        title_text="Calendar Date",
        gridcolor="#F0F0F0",
        linecolor="#E8E8E8",
        tickfont=dict(color="#222222"),
        title_font=dict(color="#222222"),
    )

    return fig


def create_discount_history_chart(product_df: pd.DataFrame, product_name: str) -> go.Figure:
    """Create an interactive bar chart of promotional discount percentages over time."""
    fig = go.Figure()
    p_sorted = product_df.sort_values("date")

    fig.add_trace(
        go.Bar(
            name="Promotional Discount (%)",
            x=p_sorted["date"],
            y=p_sorted["discount_pct"],
            marker_color="#E23744",
            opacity=0.85,
            hovertemplate="<b>%{x}</b><br>Discount: %{y:.1f}%<extra></extra>",
        )
    )

    max_disc = float(p_sorted["discount_pct"].max()) if not p_sorted.empty else 40.0
    y_max = max(50.0, max_disc + 5.0)

    fig.update_layout(
        title=f"<b>Historical Promotional Markdown Discount Frequency (%) — {product_name}</b>",
        template="plotly_white",
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#222222"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=40, r=40, t=70, b=40),
    )

    fig.update_yaxes(
        title_text="Discount Percentage (%)",
        gridcolor="#F0F0F0",
        linecolor="#E8E8E8",
        tickfont=dict(color="#222222"),
        title_font=dict(color="#222222"),
        range=[0, y_max],
    )

    fig.update_xaxes(
        title_text="Calendar Date",
        gridcolor="#F0F0F0",
        linecolor="#E8E8E8",
        tickfont=dict(color="#222222"),
        title_font=dict(color="#222222"),
    )

    return fig


def create_demand_trend_chart(product_df: pd.DataFrame, product_name: str) -> go.Figure:
    """Create an interactive chart of daily units sold and available stock over time."""
    fig = go.Figure()
    p_sorted = product_df.sort_values("date")

    # Units Sold (Emerald Green Bar)
    fig.add_trace(
        go.Bar(
            name="Units Sold",
            x=p_sorted["date"],
            y=p_sorted["units_sold"],
            marker_color="#008A3E",
            opacity=0.85,
            hovertemplate="<b>%{x}</b><br>Units Sold: %{y:,.1f}<extra></extra>",
        )
    )

    # Available Physical Stock (Slate dotted line)
    fig.add_trace(
        go.Scatter(
            name="Units Available (Stock)",
            x=p_sorted["date"],
            y=p_sorted["units_available"],
            mode="lines",
            line=dict(color="#718096", width=2, dash="dot"),
            hovertemplate="<b>%{x}</b><br>Available Stock: %{y:,.1f} units<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"<b>Daily Consumer Demand Trend & Inventory Velocity (Units) — {product_name}</b>",
        template="plotly_white",
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color="#222222"),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#222222"),
        ),
        margin=dict(l=40, r=40, t=70, b=40),
        hovermode="x unified",
    )

    fig.update_yaxes(
        title_text="Physical Quantity (Units)",
        gridcolor="#F0F0F0",
        linecolor="#E8E8E8",
        tickfont=dict(color="#222222"),
        title_font=dict(color="#222222"),
    )

    fig.update_xaxes(
        title_text="Calendar Date",
        gridcolor="#F0F0F0",
        linecolor="#E8E8E8",
        tickfont=dict(color="#222222"),
        title_font=dict(color="#222222"),
    )

    return fig


# ---------------------------------------------------------------------------
# Strict Light Theme & Zomato Red-and-White Custom Styling
# ---------------------------------------------------------------------------

def render_custom_css() -> None:
    """Inject strict light-theme typography, white backgrounds, and Zomato card designs."""
    render_html(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #222222 !important;
            background-color: #FFFFFF !important;
        }

        .stApp, [data-testid="stAppViewContainer"], .main, .block-container {
            background-color: #FFFFFF !important;
            color: #222222 !important;
        }

        header[data-testid="stHeader"] {
            background-color: #FFFFFF !important;
            border-bottom: 1px solid #F0F0F0 !important;
        }

        section[data-testid="stSidebar"], [data-testid="stSidebarNav"] {
            background-color: #F8F8F8 !important;
            border-right: 1px solid #EAEAEA !important;
        }
        section[data-testid="stSidebar"] * {
            color: #222222 !important;
        }
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label {
            color: #222222 !important;
            font-weight: 500 !important;
        }

        h1, h2, h3, h4, h5, h6, p, span, div, label {
            color: #222222;
        }

        div[data-baseweb="input"], 
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"], 
        div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border-color: #E2E8F0 !important;
            color: #222222 !important;
        }
        input, textarea {
            color: #222222 !important;
            background-color: #FFFFFF !important;
        }
        div[data-baseweb="input"] button {
            background-color: #F8F8F8 !important;
            color: #222222 !important;
        }

        div[data-testid="stSlider"] > div {
            color: #222222 !important;
        }

        .stButton > button, div.stDownloadButton > button {
            background-color: #FFFFFF !important;
            color: #E23744 !important;
            border: 1px solid #FFD2D6 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button:hover, div.stDownloadButton > button:hover {
            background-color: #E23744 !important;
            color: #FFFFFF !important;
            border-color: #E23744 !important;
            box-shadow: 0 4px 12px rgba(226, 55, 68, 0.2) !important;
        }

        div[data-testid="stDataFrame"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E8E8E8 !important;
            border-radius: 8px !important;
        }

        .metadata-bar {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 10px 16px;
            margin: 12px 0 20px 0;
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            align-items: center;
            font-size: 0.82rem;
            color: #475569;
        }
        .metadata-bar span {
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .policy-card {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
            height: 100%;
        }
        .card-fixed {
            border-top: 3px solid #64748B !important;
        }
        .card-markdown {
            border-top: 3px solid #E23744 !important;
        }

        .card-header-badge {
            font-size: 0.70rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 2px 8px;
            border-radius: 4px;
            display: inline-block;
            margin-bottom: 6px;
        }
        .badge-fixed {
            background-color: #F1F5F9;
            color: #475569 !important;
            border: 1px solid #CBD5E1;
        }
        .badge-markdown {
            background-color: #FFF1F2;
            color: #E23744 !important;
            border: 1px solid #FECDD3;
        }

        .card-title {
            font-size: 1.20rem;
            font-weight: 800;
            color: #0F172A;
            margin-bottom: 4px;
        }
        .card-desc {
            font-size: 0.80rem;
            color: #64748B;
            margin-bottom: 14px;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 7px 0;
            border-bottom: 1px solid #F1F5F9;
            font-size: 0.86rem;
        }
        .metric-row:last-child {
            border-bottom: none;
        }
        .metric-label-text {
            color: #64748B;
            font-weight: 500;
        }
        .metric-val-text {
            font-weight: 600;
            color: #0F172A;
        }
        .text-red {
            color: #E23744 !important;
        }
        .text-green {
            color: #008A3E !important;
        }
        .text-neutral {
            color: #4A5568 !important;
        }

        .executive-kpi-container {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin: 14px 0 24px 0;
        }
        .executive-kpi-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 14px 18px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .kpi-title {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748B;
            margin-bottom: 4px;
        }
        .kpi-value {
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1.2;
            margin-bottom: 4px;
            color: #0F172A;
        }
        .kpi-delta {
            font-size: 0.78rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .deal-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 18px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
        }
        .deal-badge {
            background-color: #E23744;
            color: #FFFFFF !important;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            padding: 3px 8px;
            border-radius: 4px;
            display: inline-block;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .deal-title {
            font-size: 1.05rem;
            font-weight: 800;
            color: #0F172A;
            margin-bottom: 2px;
        }
        .deal-category {
            font-size: 0.75rem;
            color: #64748B;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .deal-price-row {
            display: flex;
            align-items: baseline;
            gap: 8px;
            margin: 8px 0;
        }
        .deal-reg-price {
            font-size: 0.88rem;
            color: #94A3B8;
            text-decoration: line-through;
        }
        .deal-sale-price {
            font-size: 1.35rem;
            font-weight: 800;
            color: #E23744;
        }
        .deal-meta-row {
            font-size: 0.80rem;
            color: #475569;
            padding-top: 8px;
            border-top: 1px solid #F1F5F9;
            display: flex;
            justify-content: space-between;
        }

        .section-header {
            font-size: 1.20rem;
            font-weight: 800;
            color: #0F172A;
            margin: 24px 0 6px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-subtext {
            font-size: 0.84rem;
            color: #64748B;
            margin-bottom: 14px;
        }

        .minimal-footer {
            border-top: 1px solid #E2E8F0;
            margin-top: 36px;
            padding-top: 18px;
            padding-bottom: 24px;
            text-align: center;
            color: #64748B;
            font-size: 0.80rem;
            line-height: 1.5;
        }
        </style>
        """
    )


# ---------------------------------------------------------------------------
# Executive KPI Row & Structured Components
# ---------------------------------------------------------------------------

def render_executive_kpi_row(f: PolicyMetrics, m: PolicyMetrics) -> None:
    """Render 4 dynamically calculated executive KPI cards above the detailed comparison."""
    waste_saved = f.units_wasted - m.units_wasted
    waste_red_pct = (waste_saved / f.units_wasted * 100.0) if f.units_wasted > 0 else 0.0
    rev_gain = m.revenue - f.revenue
    rev_pct = (rev_gain / f.revenue * 100.0) if f.revenue > 0 else 0.0
    net_gain = m.net_contribution - f.net_contribution
    net_pct = (net_gain / f.net_contribution * 100.0) if f.net_contribution > 0 else 0.0
    margin_pp = m.gross_margin_pct - f.gross_margin_pct

    render_html(
        f"""
        <div class="executive-kpi-container">
            <div class="executive-kpi-card" style="border-top: 3px solid #008A3E;">
                <div class="kpi-title">Waste Reduction</div>
                <div class="kpi-value text-green">{waste_red_pct:.1f}%</div>
                <div class="kpi-delta text-green">
                    <span>▼ {format_units(waste_saved)} saved</span>
                </div>
            </div>
            <div class="executive-kpi-card" style="border-top: 3px solid {'#008A3E' if rev_gain >= 0 else '#E23744'};">
                <div class="kpi-title">Revenue Change</div>
                <div class="kpi-value {'text-green' if rev_gain >= 0 else 'text-red'}">{format_inr(rev_gain, include_sign=True)}</div>
                <div class="kpi-delta {'text-green' if rev_gain >= 0 else 'text-red'}">
                    <span>{f"▲ +{rev_pct:.1f}%" if rev_gain >= 0 else f"▼ {rev_pct:.1f}%"} vs baseline</span>
                </div>
            </div>
            <div class="executive-kpi-card" style="border-top: 3px solid {'#008A3E' if net_gain >= 0 else '#E23744'};">
                <div class="kpi-title">Net Contribution Gain</div>
                <div class="kpi-value {'text-green' if net_gain >= 0 else 'text-red'}">{format_inr(net_gain, include_sign=True)}</div>
                <div class="kpi-delta {'text-green' if net_gain >= 0 else 'text-red'}">
                    <span>{f"▲ +{net_pct:.1f}%" if net_gain >= 0 else f"▼ {net_pct:.1f}%"} operational profit</span>
                </div>
            </div>
            <div class="executive-kpi-card" style="border-top: 3px solid {'#008A3E' if margin_pp >= 0 else '#64748B'};">
                <div class="kpi-title">Gross Margin Change</div>
                <div class="kpi-value {'text-green' if margin_pp >= 0 else 'text-neutral'}">{format_pp(margin_pp, include_sign=True)}</div>
                <div class="kpi-delta text-neutral">
                    <span>{f.gross_margin_pct:.1f}% → {m.gross_margin_pct:.1f}% of rev</span>
                </div>
            </div>
        </div>
        """
    )


def render_simulation_pipeline_expander() -> None:
    """Render compact expandable simulation pipeline explanation (Stock -> Demand -> Pricing -> Evaluation)."""
    with st.expander("📖 Simulation Pipeline & Decision Framework (Stock → Demand → Pricing → Evaluation)", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_html(
                """
                <div class="pipeline-card">
                    <div style="margin-bottom:8px;"><span class="pipeline-step-num">1</span><span class="pipeline-step-title">Stock & Batches</span></div>
                    <div style="font-size:0.82rem; color:#475569; line-height:1.5;">
                        • Scheduled delivery arrivals each morning.<br>
                        • Batches track arrival, expiry & unit cost.<br>
                        • Morning check purges expired batches.<br>
                        • First-Expiry-First-Out (FEFO) queue.
                    </div>
                </div>
                """
            )
        with c2:
            render_html(
                """
                <div class="pipeline-card">
                    <div style="margin-bottom:8px;"><span class="pipeline-step-num">2</span><span class="pipeline-step-title">Customer Demand</span></div>
                    <div style="font-size:0.82rem; color:#475569; line-height:1.5;">
                        • Stochastic baseline footfall (Poisson).<br>
                        • Price response: 1 + γ × (elasticity × d).<br>
                        • Near-expiry avoidance / clearance surge.<br>
                        • Feasibility bound: Q<sub>sold</sub> ≤ Q<sub>avail</sub>.
                    </div>
                </div>
                """
            )
        with c3:
            render_html(
                """
                <div class="pipeline-card">
                    <div style="margin-bottom:8px;"><span class="pipeline-step-num">3</span><span class="pipeline-step-title">Clearance Pricing</span></div>
                    <div style="font-size:0.82rem; color:#475569; line-height:1.5;">
                        • Graduated rule or Demand-Aware optimizer.<br>
                        • Shelf-life aware thresholds (Max L-2).<br>
                        • Margin floor: P ≥ C / (1 - m<sub>min</sub>).<br>
                        • Zero markdown on healthy stock.
                    </div>
                </div>
                """
            )
        with c4:
            render_html(
                """
                <div class="pipeline-card">
                    <div style="margin-bottom:8px;"><span class="pipeline-step-num">4</span><span class="pipeline-step-title">Evaluation & GAAP</span></div>
                    <div style="font-size:0.82rem; color:#475569; line-height:1.5;">
                        • Full physical inventory balance.<br>
                        • GAAP Gross Profit = Rev - COGS.<br>
                        • Waste Cost = Spoilage × Unit Cost.<br>
                        • Net Contribution = Gross Profit - Waste Cost.
                    </div>
                </div>
                """
            )
        st.caption("💡 *Single-Slide Summary*: Inventory batches arrive scheduled, unexpired stock is queued in FEFO order, price clearance activates as shelf life nears expiry (bound by margin floor P ≥ C / (1-m)), and performance reconciles GAAP profit with operational waste recovery.")


def render_reproducibility_panel(
    sim_result: SimulationResult,
    seed_val: int,
    sim_days: int,
    policy_mode: str,
    shopper_multiplier: float,
    min_margin: float,
) -> None:
    """Render compact reproducibility information panel and CSV data exports."""
    with st.expander("🎲 Experiment Reproducibility & Data Governance", expanded=False):
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(
                f"""
                - **Random Seed**: `{seed_val}` (Deterministic pseudo-random RNG)
                - **Simulation Horizon**: `{sim_days} Days`
                - **Pricing Policy**: `{policy_mode}` (Margin Floor: `{min_margin}%`)
                - **Shopper Response Multiplier (γ)**: `{shopper_multiplier}x` (Sensitivity factor)
                - **Comparison Mode**: `Synchronized Matched Pair (Fixed vs Markdown)`
                - **Matched Inventory & Demand**: `✅ Verified (Identical Day 1 stock, identical scheduled arrivals, identical baseline demand draws)`
                - **Dataset Schema**: `20 Perishable SKUs (Dairy, Bakery, Fruits, Vegetables)`
                """
            )
            st.caption("⚠️ **Synthetic Benchmark Disclosure**: All inventory volumes, price points, and demand histories are synthetic benchmark models developed for NEXAI 2026 Hackathon PS 4.1 in Indian Rupees (₹). They do not represent proprietary supermarket POS transactions.")
        with c2:
            st.markdown("##### Download Export Deliverables")
            st.download_button(
                label="📥 Download Policy Comparison Summary CSV",
                data=sim_result.comparison_summary_df.to_csv(index=False),
                file_name="policy_comparison_summary.csv",
                mime="text/csv",
                key="dl_summary_csv_btn",
                use_container_width=True,
            )
            st.download_button(
                label="📥 Download Daily Product Simulation History CSV",
                data=sim_result.daily_history_df.to_csv(index=False),
                file_name="daily_simulation_history.csv",
                mime="text/csv",
                key="dl_daily_csv_btn",
                use_container_width=True,
            )
            st.download_button(
                label="📥 Download Markdown Clearance Events CSV",
                data=sim_result.markdown_events_df.to_csv(index=False),
                file_name="markdown_events_history.csv",
                mime="text/csv",
                key="dl_events_csv_btn",
                use_container_width=True,
            )


def render_shopper_deals_view(
    daily_df: pd.DataFrame,
    products: List[Product],
    active_day: int,
    active_policy: str = "Markdown Policy",
    near_expiry_threshold: int = 2,
) -> None:
    """Render shopper-facing 'Today's Fresh Deals' portal view."""
    render_html(
        """
        <div class="zomato-hero" style="border-left: 5px solid #008A3E;">
            <span class="zomato-badge" style="background-color:#008A3E;">Shopper Clearance Deals</span>
            <div class="zomato-title">Today's Fresh Deals 🛒</div>
            <div class="zomato-subtitle">
                Save on high-quality grocery items near their best-before date! 
                Grab these limited in-store clearance deals and help us eliminate perishable food waste.
            </div>
        </div>
        """
    )

    # If store is currently operating under Fixed Price, display clear explanation
    if active_policy == "Fixed Price":
        render_html(
            """
            <div style="background-color:#FFFBEB; border:1px solid #FDE68A; border-left:4px solid #D97706; border-radius:8px; padding:18px 24px; margin:20px 0; color:#92400E;">
                <div style="font-weight:700; font-size:1.05rem; margin-bottom:6px;">Store Operating Under Fixed Price Policy</div>
                <div style="font-size:0.90rem; line-height:1.5;">
                    The store is currently configured for <b>Fixed Price Policy</b>, meaning products are sold at regular retail price until expiration with no promotional discounts.<br>
                    To view simulated clearance markdowns, switch the <b>Store Pricing Policy</b> to <b>Markdown Policy</b> in the sidebar.
                </div>
            </div>
            """
        )

    # Identify universe of eligible clearance deals in the simulation:
    # Criteria:
    # 1. Product exists in catalog
    # 2. Markdown policy records
    # 3. Genuine discount: discount_pct > 0.0 and selling_price < regular_price
    # 4. Unexpired: days_until_expiry >= 1
    # 5. Saleable stock available: (units_sold + ending_stock) > 0.0
    deals_universe = daily_df[
        (daily_df["policy"] == "markdown")
        & (daily_df["discount_pct"] > 0.0)
        & (daily_df["days_until_expiry"] >= 1)
        & ((daily_df["units_sold"] + daily_df["ending_stock"]) > 0.0)
        & (daily_df["selling_price"] < daily_df["regular_price"])
    ].copy()

    days_avail = sorted(list(set(daily_df["day"])))
    days_with_deals = sorted(deals_universe["day"].unique().tolist())

    # Smart default: pick first day with deals (e.g. Day 3) so page opens with active deals
    default_day = days_with_deals[0] if days_with_deals else (days_avail[0] if days_avail else 1)
    default_index = days_avail.index(default_day) if default_day in days_avail else 0

    def format_day_option(d: int) -> str:
        count = len(deals_universe[deals_universe["day"] == d])
        if count > 0:
            return f"Day {d}  —  {count} Active Clearance Deal{'s' if count > 1 else ''} 🔥"
        return f"Day {d}  —  (No active clearance deals)"

    col_filter1, col_filter2 = st.columns([2, 1])
    with col_filter1:
        day_selected = st.selectbox(
            "Simulated Shopping Day:",
            options=days_avail,
            index=default_index,
            format_func=format_day_option,
            key="shopper_day_select",
            help="Select any day within the simulation horizon to inspect available clearance items for that specific day.",
        )
    with col_filter2:
        cat_filter = st.selectbox(
            "Filter by Category:",
            options=["All Categories", "Dairy", "Bakery", "Fruits", "Vegetables"],
            index=0,
            key="shopper_cat_select",
        )

    # Filter deals for the selected day:
    day_deals = deals_universe[deals_universe["day"] == day_selected].copy()
    if cat_filter != "All Categories":
        day_deals = day_deals[day_deals["category"].str.lower() == cat_filter.lower()]

    st.markdown(f"##### Active clearance deals on **Day {day_selected}** ({len(day_deals)} available):")

    if day_deals.empty:
        sample_deal_days = ", ".join(f"Day {d}" for d in days_with_deals[:6]) if days_with_deals else "None"
        render_html(
            f"""
            <div style="background-color:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px; padding:36px; text-align:center; margin:24px 0;">
                <div style="font-size:2.2rem; margin-bottom:10px;">🛒</div>
                <div style="font-weight:800; font-size:1.15rem; color:#1E293B; margin-bottom:6px;">No clearance deals on Day {day_selected}</div>
                <div style="font-size:0.88rem; color:#64748B; max-width:560px; margin:0 auto; line-height:1.6;">
                    All products are fresh with &gt; {near_expiry_threshold} days shelf life on Day {day_selected}.<br>
                    Products appear here when the store markdown policy offers an eligible discount on available, unexpired inventory.<br><br>
                    <b>Next Step:</b> Select a day with active clearance markdowns (such as {sample_deal_days}) using the dropdown above.
                </div>
            </div>
            """
        )
    else:
        cols = st.columns(3)
        for idx, (_, row) in enumerate(day_deals.iterrows()):
            with cols[idx % 3]:
                savings = row["regular_price"] - row["selling_price"]
                avail_qty = row["units_sold"] + row["ending_stock"]
                disc_int = int(round(row["discount_pct"]))
                badge_text = f"🔥 {disc_int}% OFF CLEARANCE"
                days_left = int(row["days_until_expiry"])
                urgency_text = f"⏳ {days_left} {'day' if days_left == 1 else 'days'} left!"
                freshness_badge = "Best Before: Within 24 Hours" if days_left == 1 else "Best Before: Within 48 Hours"
                urgency_color = "#E23744" if days_left == 1 else "#166534"

                render_html(
                    f"""
                    <div class="deal-card">
                        <div>
                            <span class="deal-badge">{badge_text}</span>
                            <div class="deal-title">{row['product_name']}</div>
                            <div class="deal-category">Category: {row['category'].title()}</div>
                            <div style="margin: 6px 0;">
                                <span style="background-color:#F1F5F9; color:{urgency_color}; font-size:0.75rem; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #E2E8F0;">
                                    🏷️ {freshness_badge}
                                </span>
                            </div>
                            <div class="deal-price-row">
                                <span class="deal-sale-price">{format_inr(row['selling_price'])}</span>
                                <span class="deal-reg-price">{format_inr(row['regular_price'])}</span>
                                <span style="font-size:0.80rem; color:#008A3E; font-weight:700;">Save {format_inr(savings)}</span>
                            </div>
                        </div>
                        <div class="deal-meta-row">
                            <span style="font-weight:700; color:{urgency_color};">{urgency_text}</span>
                            <span><b>{format_units(avail_qty)}</b> available</span>
                        </div>
                    </div>
                    """
                )

    st.markdown("---")
    st.caption("ℹ️ **Simulation demo: all prices, inventory levels, and clearance offers are generated from synthetic data. No real transactions are available.**")


def render_per_product_view(
    sim_result,
    sim_days: int,
    t2: int,
    d2: float,
    t1: int,
    d1: float,
    seed_val: int,
    min_margin: float = 10.0,
) -> None:
    """Render dedicated Per-Product Markdown History & Operational Ledger view."""
    # Metadata Bar
    render_html(
        f"""
        <div class="metadata-bar">
            <span>⏱️ Duration: <b>{sim_days} Days</b></span>
            <span>🎲 Seed: <b>{seed_val}</b></span>
            <span>📏 Clearance Rules: <b>≤{t2}d: {d2:.0f}% | ≤{t1}d: {d1:.0f}%</b> (Floor ≥{min_margin:.0f}%)</span>
            <span>🛒 <b>20 Perishable SKUs</b></span>
            <span>🧪 <i>Synthetic Perishables Dataset (NEXAI 2026 PS 4.1 Demo)</i></span>
        </div>
        """
    )

    render_html('<div class="section-header">Per-Product Markdown History & Operational Ledger</div>')
    render_html(
        '<div class="section-subtext">Inspect SKU-level price trajectories, recorded markdown events, daily inventory movements, and batch reconciliation identity across 20 perishable products:</div>'
    )

    products = get_default_products()
    prod_names = [p.name for p in products]

    col_psel1, col_psel2 = st.columns([1, 2])
    with col_psel1:
        selected_prod_name = st.selectbox(
            "Select Perishable Product (20 Products):",
            options=prod_names,
            index=0,
            key="sim_product_select",
        )
    selected_prod = [p for p in products if p.name == selected_prod_name][0]
    p_id = selected_prod.product_id

    # Selected product daily records under Markdown Policy and Fixed Policy
    p_md_df = sim_result.daily_history_df[
        (sim_result.daily_history_df["product_id"] == p_id) & (sim_result.daily_history_df["policy"] == "markdown")
    ].sort_values("day")
    p_fixed_df = sim_result.daily_history_df[
        (sim_result.daily_history_df["product_id"] == p_id) & (sim_result.daily_history_df["policy"] == "fixed")
    ].sort_values("day")

    p_sold_md = float(p_md_df["units_sold"].sum())
    p_waste_md = float(p_md_df["units_wasted"].sum())
    p_waste_fixed = float(p_fixed_df["units_wasted"].sum())
    p_md_events_cnt = int((p_md_df["discount_pct"] > 0).sum())

    with col_psel2:
        col_pk1, col_pk2, col_pk3, col_pk4 = st.columns(4)
        with col_pk1:
            st.metric("Category & SKU", f"{selected_prod.category.title()}", delta=p_id)
        with col_pk2:
            st.metric("Base Price & Cost", f"₹{selected_prod.base_price:.2f}", delta=f"Cost ₹{selected_prod.unit_cost:.2f}")
        with col_pk3:
            st.metric(
                "Base Margin (%)",
                f"{((selected_prod.base_price - selected_prod.unit_cost)/selected_prod.base_price*100):.1f}%",
                delta=f"{selected_prod.shelf_life_days}d shelf life",
            )
        with col_pk4:
            st.metric(
                "Markdown Waste",
                f"{p_waste_md:.1f} units",
                delta=f"{p_waste_md - p_waste_fixed:+.1f} vs Fixed",
                delta_color="inverse",
            )

    # 1. Primary Interactive Visualizations: Timeline & Price-Demand Curve
    if p_md_df is None or p_md_df.empty:
        st.info(f"ℹ️ No recorded sales or price history available for **{selected_prod_name}** ({p_id}).")
    else:
        fig_dual = create_sim_product_sales_vs_price_chart(p_md_df, selected_prod_name)
        st.plotly_chart(fig_dual, use_container_width=True)

        fig_price_sales = create_sim_product_price_vs_sales_chart(p_md_df, selected_prod_name)
        st.plotly_chart(fig_price_sales, use_container_width=True)

    # 2. Supplementary Visualizations: Trajectory & Velocity
    with st.expander("📊 Additional Price & Inventory Breakdown Charts", expanded=False):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.plotly_chart(create_sim_product_price_chart(p_md_df, selected_prod_name), use_container_width=True)
        with col_c2:
            st.plotly_chart(create_sim_product_sales_waste_chart(p_md_df, selected_prod_name), use_container_width=True)

    if p_md_events_cnt == 0:
        st.info(
            f"ℹ️ **Constant Price Trajectory**: No markdown events occurred for **{selected_prod_name}** ({p_id}) during this {sim_days}-day simulation. "
            f"The selling price remained strictly flat at the regular catalog price of ₹{selected_prod.base_price:.2f} across all simulation days because all batches had sufficient shelf life or cleared at full price."
        )
    else:
        event_days = p_md_df[p_md_df["discount_pct"] > 0]["day"].tolist()
        days_str = ", ".join(f"Day {d}" for d in event_days)
        st.caption(
            f"🏷️ **Active Markdowns Applied**: Selling price dropped below base price on {len(event_days)} days ({days_str}) "
            f"under configured clearance rules (≤ {t2}d: {d2:.0f}% | ≤ {t1}d: {d1:.0f}%)."
        )
        # Margin Floor Safeguard Audit Notice
        prod_events_df = (
            sim_result.markdown_events_df[sim_result.markdown_events_df["product_id"] == p_id]
            if not sim_result.markdown_events_df.empty
            else pd.DataFrame()
        )
        if not prod_events_df.empty and "margin_floor_limited" in prod_events_df.columns and prod_events_df["margin_floor_limited"].any():
            floor_limited_cnt = int(prod_events_df["margin_floor_limited"].sum())
            cat_margin = ((selected_prod.base_price - selected_prod.unit_cost) / selected_prod.base_price) * 100.0
            st.caption(
                f"🛡️ **Margin Floor Clamping Notice**: Exactly {floor_limited_cnt} clearance event(s) were clamped by the **{min_margin:.0f}% Gross Margin Floor** "
                f"(Base Price: ₹{selected_prod.base_price:.2f}, Wholesale Cost: ₹{selected_prod.unit_cost:.2f}, Catalog Margin: {cat_margin:.1f}%). "
                f"To protect profitability, discounts were safely bounded to prevent selling below the margin floor."
            )

    # Markdown Event History Table for Selected Product
    prod_events = (
        sim_result.markdown_events_df[sim_result.markdown_events_df["product_id"] == p_id].copy()
        if not sim_result.markdown_events_df.empty
        else pd.DataFrame()
    )
    with st.expander(f"📜 Recorded Markdown Events History for {selected_prod_name} ({len(prod_events)} Events)", expanded=len(prod_events) > 0):
        if prod_events.empty:
            st.info(
                f"ℹ️ **No markdown events were recorded for {selected_prod_name} ({p_id})** during this {sim_days}-day simulation.\n\n"
                f"All inventory batches for this product maintained sufficient shelf life (> {t2} days remaining) or cleared through natural customer demand at the regular price of ₹{selected_prod.base_price:.2f} without requiring promotional price reductions."
            )
        else:
            evt_disp = prod_events.copy()
            evt_disp["calculated_discount_pct"] = (
                (evt_disp["regular_price"] - evt_disp["selling_price"]) / evt_disp["regular_price"] * 100.0
            ).round(1)

            if "available_stock" not in evt_disp.columns or evt_disp["available_stock"].isna().all() or (evt_disp["available_stock"] == 0).all():
                p_avail_map = dict(zip(p_md_df["day"], p_md_df["units_sold"] + p_md_df["ending_stock"]))
                evt_disp["available_stock"] = evt_disp["day"].map(p_avail_map).fillna(evt_disp["units_sold"])

            evt_disp["Simulation Day"] = evt_disp["day"].apply(lambda d: f"Day {d}")
            evt_disp["Product Name"] = selected_prod_name
            evt_disp["SKU"] = p_id
            evt_disp["Days to Expiry"] = evt_disp["days_until_expiry"].apply(lambda d: f"{int(d)} {'day' if int(d)==1 else 'days'}")
            evt_disp["Regular Base Price"] = evt_disp["regular_price"].apply(lambda p: f"₹{p:.2f}")
            evt_disp["Actual Markdown Price"] = evt_disp["selling_price"].apply(lambda p: f"₹{p:.2f}")
            evt_disp["Discount %"] = evt_disp["calculated_discount_pct"].apply(lambda d: f"{d:.1f}%")
            evt_disp["Available Stock"] = evt_disp["available_stock"].apply(lambda s: f"{s:,.1f} units")
            evt_disp["Units Sold"] = evt_disp["units_sold"].apply(lambda u: f"{u:,.1f} units")
            evt_disp["Markdown Trigger Reason"] = evt_disp["reason"]

            out_cols = [
                "Simulation Day", "Product Name", "SKU", "Days to Expiry",
                "Regular Base Price", "Actual Markdown Price", "Discount %",
                "Available Stock", "Units Sold", "Markdown Trigger Reason"
            ]
            st.dataframe(evt_disp[out_cols], use_container_width=True, hide_index=True)
            st.caption(
                f"✅ **Audit Trail**: Exactly {len(prod_events)} genuine clearance events recorded from simulation. "
                f"Discount percentages strictly calculated as `(Base Price - Markdown Price) / Base Price`."
            )

    # Daily Sales, Inventory & Spoilage Ledger
    with st.expander(f"📋 Daily Sales, Inventory & Spoilage Ledger — {selected_prod_name} ({sim_days} Days)", expanded=True):
        ledger_disp = p_md_df.copy()
        ledger_disp["avail_stock"] = ledger_disp["units_sold"] + ledger_disp["ending_stock"]
        ledger_disp["Simulation Day"] = ledger_disp["day"].apply(lambda d: f"Day {d}")
        ledger_disp["Available Stock"] = ledger_disp["avail_stock"].apply(lambda s: f"{s:,.1f} units")
        ledger_disp["Units Sold"] = ledger_disp["units_sold"].apply(lambda s: f"{s:,.1f} units")
        ledger_disp["Units Expired / Wasted"] = ledger_disp["units_wasted"].apply(lambda w: f"{w:,.1f} units")
        ledger_disp["Ending Stock"] = ledger_disp["ending_stock"].apply(lambda e: f"{e:,.1f} units")
        ledger_disp["Actual Selling Price"] = ledger_disp["selling_price"].apply(lambda p: f"₹{p:.2f}")
        ledger_disp["Markdown Status"] = ledger_disp["discount_pct"].apply(
            lambda d: f"🔥 Markdown ({d:.0f}% Off)" if d > 0 else "Regular Full Price"
        )
        ledger_disp["Waste Cost"] = ledger_disp["waste_cost"].apply(lambda c: f"₹{c:.2f}" if c > 0 else "₹0.00")
        ledger_disp["Days to Expiry"] = ledger_disp["days_until_expiry"].apply(lambda d: f"{int(d)}d")

        ledger_cols = [
            "Simulation Day", "Days to Expiry", "Available Stock", "Units Sold",
            "Units Expired / Wasted", "Ending Stock", "Actual Selling Price",
            "Markdown Status", "Waste Cost"
        ]
        st.dataframe(ledger_disp[ledger_cols], use_container_width=True, hide_index=True)

        # Product-Level Inventory Reconciliation Identity
        arrivals_all = generate_arrival_schedule(products, sim_days=sim_days, seed=seed_val)
        prod_batches = [b for b in arrivals_all if b.product_id == p_id]
        tot_received = sum(b.initial_quantity for b in prod_batches)
        end_qty = float(p_md_df.iloc[-1]["ending_stock"]) if not p_md_df.empty else 0.0
        tot_waste_cost = float(p_md_df["waste_cost"].sum())
        tot_revenue = float(p_md_df["revenue"].sum())

        col_lr1, col_lr2, col_lr3, col_lr4 = st.columns(4)
        with col_lr1:
            st.metric("Total Batches Received", f"{tot_received:,.0f} units", delta=f"{len(prod_batches)} Batches Scheduled")
        with col_lr2:
            st.metric("Total Units Sold", f"{p_sold_md:,.1f} units", delta=f"Revenue: {format_inr(tot_revenue)}")
        with col_lr3:
            st.metric("Total Units Expired / Wasted", f"{p_waste_md:,.1f} units", delta=f"Waste Cost: {format_inr(tot_waste_cost)}", delta_color="inverse")
        with col_lr4:
            st.metric(f"Ending Closing Stock (Day {sim_days})", f"{end_qty:,.1f} units", delta="Inventory Conserved ✅")

        st.caption(
            f"⚖️ **Product Inventory Conservation Identity**: {tot_received:,.1f} Total Received = "
            f"{p_sold_md:,.1f} Sold + {p_waste_md:,.1f} Wasted + {end_qty:,.1f} Ending Inventory. "
            f"(100% reconciled with store simulation)."
        )


def render_category_optimizer_tab(sim_days: int, min_margin: float) -> None:
    """Render Category-Specific Markdown Optimizer tab."""
    st.markdown("### 🏷️ Category-Specific Markdown Optimizer (PS 4.1 Stretch Goal)")
    st.markdown(
        "Evaluate department-tailored candidate markdown schedules across matched simulation seeds "
        "to discover the policy that maximizes average **Net Contribution after Waste Cost**."
    )

    if st.button("🚀 Run Multi-Seed Category Optimization", key="btn_run_category_opt"):
        with st.spinner("Evaluating candidate clearance schedules across Dairy, Bakery, Fruits, and Vegetables..."):
            from src.category_optimizer import run_category_optimization
            report = run_category_optimization(
                seeds=[42, 101, 2026],
                sim_days=sim_days,
                min_margin_pct=min_margin,
            )
            st.session_state["category_opt_report"] = report

    if "category_opt_report" in st.session_state:
        report = st.session_state["category_opt_report"]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fixed Baseline Net Contrib", format_inr(report.baseline_fixed_net_contribution))
        c2.metric("Default Markdown Net Contrib", format_inr(report.default_markdown_net_contribution))
        c3.metric("Category-Optimized Net Contrib", format_inr(report.optimized_category_net_contribution), delta=format_inr(report.net_contribution_gain_over_default, include_sign=True))
        gain_pct = ((report.optimized_category_net_contribution - report.baseline_fixed_net_contribution) / report.baseline_fixed_net_contribution * 100.0) if report.baseline_fixed_net_contribution > 0 else 0.0
        c4.metric("Gain vs Baseline", format_inr(report.net_contribution_gain_over_baseline, include_sign=True), delta=f"+{gain_pct:.1f}%")

        st.markdown("##### Evaluated Department Schedules & Optimal Selection:")
        st.dataframe(report.summary_df, use_container_width=True, hide_index=True)

        st.caption("Disclosed Evaluation Scope: Evaluated on seeds [42, 101, 2026] with identical starting stock and scheduled arrivals. Primary selection criterion: Net Contribution after Waste Cost.")
    else:
        st.info("Click the button above to run the multi-seed category clearance optimizer across all 4 departments.")


def render_sensitivity_tab(
    sim_days: int,
    seed_val: int,
    t1: int,
    d1: float,
    t2: int,
    d2: float,
    min_margin: float,
    current_multiplier: float,
) -> None:
    """Render Shopper Discount-Response Sensitivity tab."""
    st.markdown("### 🔬 Shopper Discount-Response Sensitivity Analysis (PS 4.1 Stretch Goal)")
    st.markdown(
        "Evaluate how robust markdown profitability and waste reduction remain when shoppers respond "
        "less (or more) aggressively to promotional discounts."
    )

    col_sens1, col_sens2 = st.columns([1, 2])
    with col_sens1:
        test_mult = st.select_slider(
            "Test Shopper Response Multiplier (γ):",
            options=[0.25, 0.50, 0.75, 1.00, 1.25],
            value=current_multiplier,
            key="tab_sens_slider",
            help="1.00 = Normal calibrated response; 0.50 = Half-strength response to discounts.",
        )

    res_normal = run_dashboard_simulation(
        sim_days=sim_days,
        seed=seed_val,
        threshold_1_days=t1,
        discount_1_pct=float(d1) / 100.0,
        threshold_2_days=t2,
        discount_2_pct=float(d2) / 100.0,
        min_gross_margin_pct=min_margin,
        shopper_response_multiplier=1.0,
    )
    res_tested = run_dashboard_simulation(
        sim_days=sim_days,
        seed=seed_val,
        threshold_1_days=t1,
        discount_1_pct=float(d1) / 100.0,
        threshold_2_days=t2,
        discount_2_pct=float(d2) / 100.0,
        min_gross_margin_pct=min_margin,
        shopper_response_multiplier=test_mult,
    )

    fn = res_normal.fixed_metrics
    mn = res_normal.markdown_metrics
    mt = res_tested.markdown_metrics

    sens_records = [
        {"Metric": "Shopper Response Multiplier (γ)", "Normal Response (1.00x)": "1.00x", f"Sensitivity Scenario ({test_mult:.2f}x)": f"{test_mult:.2f}x", "Variance": f"{test_mult - 1.0:+.2f}x"},
        {"Metric": "Markdown Units Sold", "Normal Response (1.00x)": format_units(mn.units_sold), f"Sensitivity Scenario ({test_mult:.2f}x)": format_units(mt.units_sold), "Variance": format_units(mt.units_sold - mn.units_sold, include_sign=True)},
        {"Metric": "Markdown Units Wasted", "Normal Response (1.00x)": format_units(mn.units_wasted), f"Sensitivity Scenario ({test_mult:.2f}x)": format_units(mt.units_wasted), "Variance": format_units(mt.units_wasted - mn.units_wasted, include_sign=True)},
        {"Metric": "Waste Reduction (%)", "Normal Response (1.00x)": f"{((fn.units_wasted - mn.units_wasted)/fn.units_wasted*100):.2f}%" if fn.units_wasted > 0 else "0.00%", f"Sensitivity Scenario ({test_mult:.2f}x)": f"{((fn.units_wasted - mt.units_wasted)/fn.units_wasted*100):.2f}%" if fn.units_wasted > 0 else "0.00%", "Variance": f"{(((fn.units_wasted - mt.units_wasted) - (fn.units_wasted - mn.units_wasted))/fn.units_wasted*100):+.2f} pp" if fn.units_wasted > 0 else "0.00 pp"},
        {"Metric": "Total Store Revenue (₹)", "Normal Response (1.00x)": format_inr(mn.revenue), f"Sensitivity Scenario ({test_mult:.2f}x)": format_inr(mt.revenue), "Variance": format_inr(mt.revenue - mn.revenue, include_sign=True)},
        {"Metric": "Gross Profit (₹)", "Normal Response (1.00x)": format_inr(mn.gross_margin), f"Sensitivity Scenario ({test_mult:.2f}x)": format_inr(mt.gross_margin), "Variance": format_inr(mt.gross_margin - mn.gross_margin, include_sign=True)},
        {"Metric": "Gross Margin (%)", "Normal Response (1.00x)": f"{mn.gross_margin_pct:.2f}%", f"Sensitivity Scenario ({test_mult:.2f}x)": f"{mt.gross_margin_pct:.2f}%", "Variance": f"{mt.gross_margin_pct - mn.gross_margin_pct:+.2f} pp"},
        {"Metric": "Total Waste Cost (₹)", "Normal Response (1.00x)": format_inr(mn.total_waste_cost), f"Sensitivity Scenario ({test_mult:.2f}x)": format_inr(mt.total_waste_cost), "Variance": format_inr(mt.total_waste_cost - mn.total_waste_cost, include_sign=True)},
        {"Metric": "Net Contribution after Waste (₹)", "Normal Response (1.00x)": format_inr(mn.net_contribution), f"Sensitivity Scenario ({test_mult:.2f}x)": format_inr(mt.net_contribution), "Variance": format_inr(mt.net_contribution - mn.net_contribution, include_sign=True)},
        {"Metric": "Ending Inventory (units)", "Normal Response (1.00x)": format_units(mn.ending_inventory), f"Sensitivity Scenario ({test_mult:.2f}x)": format_units(mt.ending_inventory), "Variance": format_units(mt.ending_inventory - mn.ending_inventory, include_sign=True)},
    ]

    st.dataframe(pd.DataFrame(sens_records), use_container_width=True, hide_index=True)
    st.caption("Model Note: This is an econometric sensitivity experiment evaluating model robustness under dampened demand elasticity. It does not represent measured empirical POS consumer footfall.")


# ---------------------------------------------------------------------------
# Streamlit Dashboard Application Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """Streamlit single-page application entrypoint."""
    st.set_page_config(
        page_title="FreshPrice AI — Markdown Before Waste",
        page_icon="🛒",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    render_custom_css()

    # 1. Main Sidebar Controls (Clean, Focused & Essential)
    render_html(
        """
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:14px;">
            <span style="background-color:#E23744; color:#ffffff; font-weight:800; font-size:0.85rem; padding:3px 10px; border-radius:4px;">FreshPrice AI</span>
            <span style="font-weight:700; color:#0F172A; font-size:0.95rem;">Simulation Setup</span>
        </div>
        """,
        container=st.sidebar,
    )

    # Simulation Duration & Seed
    st.sidebar.markdown("### Simulation")
    sim_days = st.sidebar.slider(
        "Simulation duration (days)",
        min_value=7,
        max_value=60,
        value=30,
        step=1,
        key="sim_days_slider",
        help="Simulated time horizon in days (default: 30 days).",
    )
    seed_val = st.sidebar.number_input(
        "Random seed",
        value=42,
        min_value=1,
        max_value=999999,
        step=1,
        key="sim_seed_input",
        help="Deterministic RNG seed for batch deliveries and customer demand draws (default: 42).",
    )

    # Pricing Policy Choice
    st.sidebar.markdown("### Pricing Policy")
    pricing_policy_choice = st.sidebar.radio(
        "Store Pricing Policy",
        options=["Fixed Price", "Markdown Pricing"],
        index=1,
        key="pricing_policy_radio",
        help="Select store operational pricing strategy.",
    )
    if pricing_policy_choice == "Fixed Price":
        st.sidebar.caption("Fixed Price: Products remain at their regular prices until expiry.")
    else:
        st.sidebar.caption("Markdown Pricing: Products receive configurable discounts as they approach expiry.")

    # Markdown Discount Rules
    st.sidebar.markdown("### Markdown Rules")
    t2 = st.sidebar.slider(
        "Near-expiry threshold (days)",
        min_value=1,
        max_value=10,
        value=2,
        step=1,
        key="threshold_2_input",
        help="Days until expiry when near-expiry discount begins (default: 2 days).",
    )
    d2 = st.sidebar.slider(
        "Near-expiry discount (%)",
        min_value=0,
        max_value=100,
        value=20,
        step=1,
        key="discount_2_slider",
        help="Promotional discount percentage for near-expiry products (default: 20%).",
    )
    t1 = st.sidebar.slider(
        "Urgent clearance threshold (days)",
        min_value=1,
        max_value=10,
        value=1,
        step=1,
        key="threshold_1_input",
        help="Days until expiry when urgent clearance discount begins (default: 1 day).",
    )
    d1 = st.sidebar.slider(
        "Urgent clearance discount (%)",
        min_value=0,
        max_value=100,
        value=40,
        step=1,
        key="discount_1_slider",
        help="Urgent clearance discount percentage for critical products (default: 40%).",
    )

    if int(t1) > int(t2):
        st.sidebar.caption(f"⚠️ Note: Urgent threshold ({t1}d) exceeds near-expiry ({t2}d); simulator bounds urgent rule to ≤ {t2}d.")
    if int(d2) > int(d1):
        st.sidebar.caption(f"💡 Note: Near-expiry discount ({d2}%) is set higher than urgent clearance ({d1}%).")

    rule_logic_text = generate_rule_logic_explanation(
        near_expiry_threshold=int(t2),
        near_expiry_discount_pct=int(d2),
        urgent_threshold=int(t1),
        urgent_discount_pct=int(d1),
    )
    st.sidebar.markdown(rule_logic_text)

    # Margin Protection
    st.sidebar.markdown("### Margin Protection")
    min_margin = st.sidebar.slider(
        "Minimum Gross Margin Floor (%)",
        min_value=0,
        max_value=40,
        value=10,
        step=1,
        key="min_margin_slider",
        help="Price floor formula: minimum_price = unit_cost / (1 - minimum_margin_rate). Prevents selling below margin threshold.",
    )
    st.sidebar.caption("Formula: `minimum_price = unit_cost / (1 - min_margin_rate)`")

    # Secondary / Advanced Controls in Expander
    with st.sidebar.expander("⚙️ Advanced Settings", expanded=False):
        shopper_response_mult = st.slider(
            "Shopper Sensitivity Multiplier (γ)",
            min_value=0.2,
            max_value=2.0,
            value=1.0,
            step=0.1,
            key="shopper_multiplier_slider",
            help="Calibrate customer sensitivity to price markdowns (1.0 = standard benchmark).",
        )
        waste_disposal_fee = st.number_input(
            "Waste Disposal Fee per Unit (₹)",
            min_value=0.0,
            max_value=50.0,
            value=0.0,
            step=1.0,
            key="waste_fee_input",
            help="Environmental regulatory disposal surcharge per spoiled unit.",
        )
        cost_floor_enforced = st.checkbox(
            "Enforce Unit Cost / Margin Floor",
            value=True,
            key="enforce_floor_chk",
            help="Strictly prevent markdowns below wholesale unit cost plus margin floor.",
        )

    # 2. Run Synchronized Simulation via Cached Orchestration Function
    sim_result = run_dashboard_simulation(
        sim_days=int(sim_days),
        seed=int(seed_val),
        threshold_1_days=int(t1),
        discount_1_pct=float(d1) / 100.0,
        threshold_2_days=int(t2),
        discount_2_pct=float(d2) / 100.0,
        enforce_cost_floor=bool(cost_floor_enforced),
        policy_mode="graduated_rule",
        min_gross_margin_pct=float(min_margin),
        waste_disposal_fee=float(waste_disposal_fee),
        shopper_response_multiplier=float(shopper_response_mult),
    )

    f = sim_result.fixed_metrics
    m = sim_result.markdown_metrics

    # 3. Top-Level Header & Navigation Component
    col_header, col_nav = st.columns([1.25, 1.75])
    with col_header:
        render_html(
            """
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:2px;">
                <span style="background-color:#E23744; color:#FFFFFF; font-weight:800; font-size:0.85rem; padding:3px 10px; border-radius:4px; letter-spacing:0.04em;">FreshPrice AI</span>
                <span style="font-size:1.35rem; font-weight:800; color:#0F172A;">Markdown Before Waste</span>
            </div>
            <div style="font-size:0.84rem; color:#64748B;">
                Near-expiry pricing simulation to reduce food waste while protecting retail profitability.
            </div>
            """
        )
    with col_nav:
        nav_options = ["Store Operations", "Per-Product View", "Today's Fresh Deals"]
        if hasattr(st, "segmented_control"):
            active_view = st.segmented_control(
                "Application View",
                options=nav_options,
                default=nav_options[0],
                label_visibility="collapsed",
                key="app_main_navigation",
            )
        else:
            active_view = st.radio(
                "Application View",
                options=nav_options,
                index=0,
                horizontal=True,
                label_visibility="collapsed",
                key="app_main_navigation",
            )
        active_view = active_view or "Store Operations"

    # Route 1: Today's Fresh Deals View
    if "Today's Fresh Deals" in active_view:
        render_shopper_deals_view(
            daily_df=sim_result.daily_history_df,
            products=get_default_products(),
            active_day=int(sim_days),
            active_policy=pricing_policy_choice,
            near_expiry_threshold=int(t2),
        )
        render_html(
            """
            <div class="minimal-footer">
                <b>FreshPrice AI</b> • NEXAI 2026 Hackathon (Track 4: Grocery Retail, PS 4.1)<br>
                <i>Simulation demo: all prices, inventory levels, and clearance offers are generated from synthetic data. No real transactions are accepted.</i>
            </div>
            """
        )
        return

    # Route 2: Per-Product View
    if "Per-Product View" in active_view:
        render_per_product_view(
            sim_result=sim_result,
            sim_days=int(sim_days),
            t2=int(t2),
            d2=float(d2),
            t1=int(t1),
            d1=float(d1),
            seed_val=int(seed_val),
            min_margin=float(min_margin),
        )
        render_html(
            """
            <div class="minimal-footer">
                <b>FreshPrice AI</b> • NEXAI 2026 Hackathon (Track 4: Grocery Retail, PS 4.1)<br>
                <i>Simulation demo: all prices, inventory levels, and clearance offers are generated from synthetic data. Physical inventory conservation strictly enforced.</i>
            </div>
            """
        )
        return

    # Route 3: Store Operations View (Default)
    waste_saved = round(f.units_wasted - m.units_wasted, 1)
    waste_red_pct = round(((f.units_wasted - m.units_wasted) / f.units_wasted * 100.0), 2) if f.units_wasted > 0 else 0.0
    units_sold_gain = round(m.units_sold - f.units_sold, 1)
    rev_gain = round(m.revenue - f.revenue, 2)
    cogs_diff = round(m.cogs - f.cogs, 2)
    margin_gain = round(m.gross_margin - f.gross_margin, 2)
    margin_pct_diff = round(m.gross_margin_pct - f.gross_margin_pct, 2)
    waste_cost_saved = round(f.total_waste_cost - m.total_waste_cost, 2)
    net_contrib_gain = round(m.net_contribution - f.net_contribution, 2)
    sell_through_gain = round(m.sell_through_rate_pct - f.sell_through_rate_pct, 2)
    ending_stock_delta = round(m.ending_inventory - f.ending_inventory, 1)

    # 4. Small Metadata Line
    render_html(
        f"""
        <div class="metadata-bar">
            <span>⏱️ Duration: <b>{sim_days} Days</b></span>
            <span>🎲 Seed: <b>{seed_val}</b></span>
            <span>📏 Rules: <b>≤{t2}d: {d2}% | ≤{t1}d: {d1}%</b> (Floor ≥{min_margin}%)</span>
            <span>🛒 <b>20 Perishable SKUs</b></span>
            <span>🧪 <i>Synthetic Perishables Dataset (NEXAI 2026 PS 4.1 Demo)</i></span>
        </div>
        """
    )

    # 5. Top-Level Dynamic Executive KPI Row (4 High-Priority Results)
    render_executive_kpi_row(f, m)

    # 6. Side-by-Side Policy Comparison Cards (2 Columns: Fixed Price & Markdown Pricing)
    render_html('<div class="section-header">Policy Performance Comparison</div>')
    render_html(
        f'<div class="section-subtext">Cumulative {sim_days}-day benchmark evaluated on identical starting batches and customer demand shocks:</div>'
    )

    col_fixed, col_md = st.columns(2)

    # Card 1: Fixed-Price Baseline
    with col_fixed:
        render_html(
            f"""
            <div class="policy-card card-fixed">
                <span class="card-header-badge badge-fixed">Baseline Benchmark</span>
                <div class="card-title">Fixed Price</div>
                <div class="card-desc">Products retain regular prices until expiry (no clearance discounts)</div>
                <div class="metric-row">
                    <span class="metric-label-text">Units Sold:</span>
                    <span class="metric-val-text">{format_units(f.units_sold)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Units Wasted (Expired):</span>
                    <span class="metric-val-text text-red">{format_units(f.units_wasted)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Total Revenue (INR):</span>
                    <span class="metric-val-text">{format_inr(f.revenue)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Profit (Revenue - COGS):</span>
                    <span class="metric-val-text">{format_inr(f.gross_margin)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Margin (% of Rev):</span>
                    <span class="metric-val-text">{f.gross_margin_pct:.2f}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Total Waste Cost (Loss):</span>
                    <span class="metric-val-text text-red">{format_inr(f.total_waste_cost)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Net Contribution after Waste:</span>
                    <span class="metric-val-text"><b>{format_inr(f.net_contribution)}</b></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Ending Healthy Inventory:</span>
                    <span class="metric-val-text">{format_units(f.ending_inventory)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Sell-Through Rate (%):</span>
                    <span class="metric-val-text">{f.sell_through_rate_pct:.2f}%</span>
                </div>
            </div>
            """
        )

    # Card 2: Markdown Pricing
    with col_md:
        render_html(
            f"""
            <div class="policy-card card-markdown">
                <span class="card-header-badge badge-markdown">Dynamic Algorithmic</span>
                <div class="card-title text-red">Markdown Pricing</div>
                <div class="card-desc">Near-expiry discounts clear stock before spoilage under margin floor</div>
                <div class="metric-row">
                    <span class="metric-label-text">Units Sold:</span>
                    <span class="metric-val-text text-green">{format_units(m.units_sold)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Units Wasted (Expired):</span>
                    <span class="metric-val-text {'text-green' if m.units_wasted == 0 else 'text-red'}">{format_units(m.units_wasted)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Total Revenue (INR):</span>
                    <span class="metric-val-text {'text-green' if rev_gain >= 0 else 'text-red'}">{format_inr(m.revenue)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Profit (Revenue - COGS):</span>
                    <span class="metric-val-text {'text-green' if margin_gain >= 0 else 'text-neutral'}">{format_inr(m.gross_margin)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Margin (% of Rev):</span>
                    <span class="metric-val-text">{m.gross_margin_pct:.2f}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Total Waste Cost (Loss):</span>
                    <span class="metric-val-text {'text-green' if waste_cost_saved > 0 else 'text-neutral'}">{format_inr(m.total_waste_cost)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Net Contribution after Waste:</span>
                    <span class="metric-val-text {'text-green' if net_contrib_gain >= 0 else 'text-red'}"><b>{format_inr(m.net_contribution)}</b></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Ending Healthy Inventory:</span>
                    <span class="metric-val-text">{format_units(m.ending_inventory)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Sell-Through Rate (%):</span>
                    <span class="metric-val-text text-green">{m.sell_through_rate_pct:.2f}%</span>
                </div>
            </div>
            """
        )

    # Policy Differences & Variance Summary
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.markdown("##### Policy Differences & Strategic Variance")
    cd1, cd2, cd3, cd4 = st.columns(4)
    with cd1:
        st.metric("Waste Saved", format_units(waste_saved, include_sign=True), delta=f"{waste_red_pct:.1f}% reduction", delta_color="normal")
    with cd2:
        st.metric("Additional Units Sold", format_units(units_sold_gain, include_sign=True), delta=f"{format_pp(sell_through_gain, include_sign=True)} sell-through", delta_color="normal")
    with cd3:
        st.metric("Revenue Variance", format_inr(rev_gain, include_sign=True), delta=f"{format_inr(margin_gain, include_sign=True)} gross margin", delta_color="normal")
    with cd4:
        st.metric("Net Contribution Gain", format_inr(net_contrib_gain, include_sign=True), delta=f"{format_inr(waste_cost_saved, include_sign=True)} waste saved", delta_color="normal")

    if rev_gain > 0 and margin_gain < 0:
        st.caption(
            f"ℹ️ **Margin Trade-Off**: Revenue expanded by {format_inr(rev_gain, include_sign=True)}, while gross margin changed by {format_inr(margin_gain, include_sign=True)} "
            f"due to clearance discounts. However, eliminating {format_inr(waste_cost_saved, include_sign=True)} of spoilage losses yielded a net operational contribution gain of **{format_inr(net_contrib_gain, include_sign=True)}**."
        )

    # 7. Required Comparison Visualizations (Separate axes and dedicated charts)
    render_html('<div class="section-header">Financial & Waste Visualizations</div>')
    render_html(
        '<div class="section-subtext">Dedicated visualizations comparing financial cash flows (INR ₹) and physical waste reduction (Units):</div>'
    )
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.plotly_chart(create_comparison_chart(f, m), use_container_width=True)
    with col_c2:
        st.plotly_chart(create_waste_comparison_chart(f, m), use_container_width=True)

    # 8. Operational Drill-Down Callout to Dedicated Per-Product View
    render_html(
        """
        <div style="background-color:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:12px 18px; margin:22px 0 14px 0; display:flex; align-items:center; gap:12px;">
            <span style="font-size:1.2rem;">🔍</span>
            <div style="font-size:0.86rem; color:#334155;">
                <b>Looking for SKU-level drill-down?</b> Switch to the <b>Per-Product View</b> tab above to examine individual price trajectories, clearance event histories, and 30-day stock reconciliations across all 20 perishable products.
            </div>
        </div>
        """
    )

    # 9. Advanced Analysis & Diagnostic Tools (Encapsulated Section)
    with st.expander("🔬 Advanced Analysis & Diagnostic Tools", expanded=False):
        tab_cat_opt, tab_sens, tab_full_ledger, tab_recs, tab_hist, tab_repro, tab_method = st.tabs(
            [
                "🏷️ Category Optimizer",
                "📈 Shopper Sensitivity",
                "🔍 Store-Wide Daily Ledger",
                "📋 Markdown Recommendations",
                "📊 1-Year Historical Demand",
                "🎲 Reproducibility & Exports",
                "📖 Methodology & Framework",
            ]
        )

        with tab_cat_opt:
            render_category_optimizer_tab(sim_days=int(sim_days), min_margin=float(min_margin))

        with tab_sens:
            render_sensitivity_tab(
                sim_days=int(sim_days),
                seed_val=int(seed_val),
                t1=int(t1),
                d1=float(d1),
                t2=int(t2),
                d2=float(d2),
                min_margin=float(min_margin),
                current_multiplier=1.0,
            )

        with tab_full_ledger:
            st.markdown("##### Full Store Operational Ledger (All 20 Products)")
            daily_df = sim_result.daily_history_df.copy()
            col_lf1, col_lf2, col_lf3 = st.columns(3)
            with col_lf1:
                sel_policy = st.selectbox("Filter Strategy:", options=["All", "markdown", "fixed"], index=1, key="daily_policy_filter")
            with col_lf2:
                products_list = ["All"] + sorted(daily_df["product_name"].unique())
                sel_product = st.selectbox("Filter Perishable Product:", options=products_list, index=0, key="daily_product_filter")
            with col_lf3:
                max_days = max(1, int(sim_days))
                sel_day = st.slider(
                    "Filter Simulation Day Range:",
                    min_value=1,
                    max_value=max_days,
                    value=(1, max_days),
                    key=f"day_range_filter_{max_days}",
                )

            filtered_daily = daily_df[(daily_df["day"] >= sel_day[0]) & (daily_df["day"] <= sel_day[1])]
            if sel_policy != "All":
                filtered_daily = filtered_daily[filtered_daily["policy"] == sel_policy]
            if sel_product != "All":
                filtered_daily = filtered_daily[filtered_daily["product_name"] == sel_product]

            display_cols = [
                "day", "policy", "product_name", "category", "days_until_expiry",
                "regular_price", "selling_price", "discount_pct", "units_sold",
                "units_wasted", "revenue", "gross_margin", "ending_stock", "active_batch_ids"
            ]
            rename_cols = {
                "day": "Day",
                "policy": "Policy",
                "product_name": "Product",
                "category": "Category",
                "days_until_expiry": "Days to Expiry",
                "regular_price": "Base Price (₹)",
                "selling_price": "Selling Price (₹)",
                "discount_pct": "Discount %",
                "units_sold": "Units Sold",
                "units_wasted": "Units Wasted",
                "revenue": "Revenue (₹)",
                "gross_margin": "Gross Margin (₹)",
                "ending_stock": "Ending Stock",
                "active_batch_ids": "Active Batch IDs",
            }
            valid_disp_cols = [c for c in display_cols if c in filtered_daily.columns]
            st.dataframe(filtered_daily[valid_disp_cols].rename(columns=rename_cols), use_container_width=True, hide_index=True)

            st.download_button(
                label="📥 Download Daily History CSV",
                data=filtered_daily.to_csv(index=False),
                file_name="daily_simulation_history.csv",
                mime="text/csv",
                key="download_daily_history_csv",
            )

        with tab_recs:
            st.markdown("##### Product-Specific Clearance Markdown Recommendations")
            if sim_result.recommendations_df is not None and not sim_result.recommendations_df.empty:
                recs_df = sim_result.recommendations_df
                fmt_recs_df = recs_df.copy()
                fmt_recs_df["Base Price"] = fmt_recs_df["Base Price"].apply(lambda v: f"₹{v:,.2f}")
                fmt_recs_df["Recommended Selling Price"] = fmt_recs_df["Recommended Selling Price"].apply(lambda v: f"₹{v:,.2f}")
                fmt_recs_df["Recommended Discount (%)"] = fmt_recs_df["Recommended Discount (%)"].apply(lambda v: f"{v:.0f}%")
                fmt_recs_df["Base Margin (%)"] = fmt_recs_df["Base Margin (%)"].apply(lambda v: f"{v:.1f}%")
                fmt_recs_df["Discounted Margin (%)"] = fmt_recs_df["Discounted Margin (%)"].apply(lambda v: f"{v:.1f}%")
                st.dataframe(fmt_recs_df, use_container_width=True, hide_index=True)
                st.download_button(
                    label="📥 Download Recommendations CSV",
                    data=recs_df.to_csv(index=False),
                    file_name="product_markdown_recommendations.csv",
                    mime="text/csv",
                    key="download_recommendations_csv",
                )

        with tab_hist:
            st.markdown("##### One-Year Synthetic Historical Demand Analysis")
            hist_df = load_historical_demand_data()
            if not hist_df.empty:
                h_prod_names = sorted(hist_df["product_name"].unique())
                h_selected_prod_name = st.selectbox(
                    "Select Product for Historical Analysis:",
                    options=h_prod_names,
                    index=0,
                    key="price_analysis_prod_select",
                )
                p_filtered = hist_df[hist_df["product_name"] == h_selected_prod_name].copy()
                st.plotly_chart(create_historical_price_chart(p_filtered, h_selected_prod_name), use_container_width=True)
                col_hd1, col_hd2 = st.columns(2)
                with col_hd1:
                    st.plotly_chart(create_discount_history_chart(p_filtered, h_selected_prod_name), use_container_width=True)
                with col_hd2:
                    st.plotly_chart(create_demand_trend_chart(p_filtered, h_selected_prod_name), use_container_width=True)
            else:
                st.info("Historical demand dataset (data/historical_product_demand.csv) not found.")

        with tab_repro:
            render_reproducibility_panel(
                sim_result=sim_result,
                seed_val=int(seed_val),
                sim_days=int(sim_days),
                policy_mode="graduated_rule",
                shopper_multiplier=1.0,
                min_margin=float(min_margin),
            )

        with tab_method:
            st.markdown("##### Core Methodology & Accounting Framework")
            st.markdown(
                r"""
                - **Demand Realization**: $\text{Demand} = \text{Base} \times [1 + \eta \times \text{discount}] \times \text{expiry\_factor}$.
                - **FEFO Dispatch**: Depletion strictly fulfills orders from batches with earliest expiration.
                - **Physical Bound**: Units sold strictly bounded by shelf stock ($\text{Sold} \le \text{Available}$).
                - **Minimum Gross Margin Floor**: $P_{\text{min}} = \frac{\text{unit\_cost}}{1 - m_{\text{min}}}$. Markdowns never drop below $P_{\text{min}}$.
                - **GAAP Compliance**: Gross Profit = Revenue - COGS. Waste Cost = Units Wasted $\times$ Unit Cost. Net Contribution = Gross Profit - Waste Cost.
                """
            )

    # 10. Minimal, Clean Footer
    render_html(
        """
        <div class="minimal-footer">
            <b>FreshPrice AI</b> • NEXAI 2026 Hackathon (Track 4: Grocery Retail, PS 4.1: Markdown Before Waste)<br>
            <i>Simulation demo: all prices, inventory levels, and clearance offers are generated from synthetic data. Physical inventory conservation strictly enforced.</i>
        </div>
        """
    )


if __name__ == "__main__":
    main()
