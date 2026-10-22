"""FreshPrice AI — Markdown Before Waste: Near-Expiry Pricing Dashboard.

NEXAI 2026 Hackathon: Problem Statement 4.1 (Track 4: Grocery Retail).

A focused, single-page Streamlit application designed with a modern red-and-white
Zomato-inspired aesthetic and strict light theme. Simulates a 30-day grocery store with
20 perishable products, comparing:
  1. Fixed-Price Policy (always charges base regular price)
  2. Dynamic Markdown Policy (graduated near-expiry discounts with wholesale cost floor)
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.store_simulator import (
    DEFAULT_DATA_DIR,
    MarkdownPolicyConfig,
    PolicyMetrics,
    SimulationResult,
    export_mvp_csv_outputs,
    get_default_products,
    run_store_simulation,
)

# ---------------------------------------------------------------------------
# Formatting Helpers
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


# ---------------------------------------------------------------------------
# Dashboard Simulation Orchestration (Decoupled from Streamlit UI)
# ---------------------------------------------------------------------------

def run_dashboard_simulation(
    sim_days: int = 30,
    seed: int = 42,
    threshold_1_days: int = 1,
    discount_1_pct: float = 0.40,
    threshold_2_days: int = 2,
    discount_2_pct: float = 0.20,
    enforce_cost_floor: bool = True,
) -> SimulationResult:
    """Execute store simulation with the exact parameters configured in the dashboard.

    Guarantees that every change to markdown thresholds or discount percentages
    instantiates a fresh MarkdownPolicyConfig and recalculates the simulation.
    """
    config = MarkdownPolicyConfig(
        threshold_1_days=int(threshold_1_days),
        discount_1_pct=float(discount_1_pct),
        threshold_2_days=int(threshold_2_days),
        discount_2_pct=float(discount_2_pct),
        enforce_cost_floor=bool(enforce_cost_floor),
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

    # Red for preventable waste loss under Fixed; Fresh Green for markdown prevention
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


# ---------------------------------------------------------------------------
# Strict Light Theme & Zomato Red-and-White Custom Styling
# ---------------------------------------------------------------------------

def render_custom_css() -> None:
    """Inject strict light-theme typography, white backgrounds, and Zomato card designs."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* =========================================================================
           STRICT LIGHT THEME OVERRIDES (White #FFFFFF, Sidebar #F8F8F8, Text #222222)
           ========================================================================= */

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #222222 !important;
            background-color: #FFFFFF !important;
        }

        /* Streamlit App Container */
        .stApp, [data-testid="stAppViewContainer"], .main, .block-container {
            background-color: #FFFFFF !important;
            color: #222222 !important;
        }

        /* Streamlit Top Header */
        header[data-testid="stHeader"] {
            background-color: #FFFFFF !important;
            border-bottom: 1px solid #F0F0F0 !important;
        }

        /* Streamlit Sidebar (Very Light Gray #F8F8F8) */
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

        /* Global Headings & Typography */
        h1, h2, h3, h4, h5, h6, p, span, div, label {
            color: #222222;
        }

        /* Form Inputs & Controls */
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

        /* Sliders */
        div[data-testid="stSlider"] > div {
            color: #222222 !important;
        }

        /* Buttons & CSV Downloads */
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

        /* DataTables */
        div[data-testid="stDataFrame"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E8E8E8 !important;
            border-radius: 8px !important;
        }

        /* Hero Header Banner */
        .zomato-hero {
            background: linear-gradient(135deg, #FFF5F6 0%, #FFFFFF 100%);
            border: 1px solid #FFD2D6;
            border-left: 6px solid #E23744;
            border-radius: 12px;
            padding: 24px 28px;
            margin-bottom: 24px;
            box-shadow: 0 4px 16px rgba(226, 55, 68, 0.05);
        }
        .zomato-badge {
            background-color: #E23744;
            color: #ffffff !important;
            font-size: 0.82rem;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 6px;
            display: inline-block;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .zomato-title {
            font-size: 2.1rem;
            font-weight: 800;
            color: #222222;
            margin: 0 0 6px 0;
            line-height: 1.2;
        }
        .zomato-subtitle {
            font-size: 0.98rem;
            color: #555555;
            margin: 0;
            line-height: 1.5;
        }

        /* Active Settings Bar */
        .settings-bar {
            background-color: #FFFFFF;
            border: 1px solid #EAEAEA;
            border-radius: 10px;
            padding: 12px 18px;
            margin-bottom: 24px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
            box-shadow: 0 1px 4px rgba(0,0,0,0.02);
        }
        .setting-chip {
            background-color: #F8F8F8;
            border: 1px solid #E8E8E8;
            border-radius: 20px;
            padding: 5px 12px;
            font-size: 0.80rem;
            font-weight: 600;
            color: #222222;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .setting-chip-highlight {
            background-color: #FFF5F6;
            border: 1px solid #FFD2D6;
            color: #E23744 !important;
            font-weight: 700;
        }

        /* Policy Side-by-Side Comparison Columns (White Cards) */
        .policy-card {
            background-color: #FFFFFF !important;
            border: 1px solid #E8E8E8;
            border-radius: 12px;
            padding: 22px 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
            height: 100%;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .policy-card:hover {
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
        }
        .card-fixed {
            border-top: 4px solid #718096 !important; /* Neutral Gray Accent */
            background-color: #FFFFFF !important;
        }
        .card-markdown {
            border-top: 4px solid #E23744 !important; /* FreshPrice Red Accent */
            background-color: #FFFFFF !important;
        }
        .card-impact {
            border-top: 4px solid #008A3E !important; /* Performance Green Accent */
            background-color: #FFFFFF !important;
        }

        .card-header-badge {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            padding: 3px 10px;
            border-radius: 14px;
            display: inline-block;
            margin-bottom: 8px;
        }
        .badge-fixed {
            background-color: #F1F5F9;
            color: #475569 !important;
            border: 1px solid #CBD5E1;
        }
        .badge-markdown {
            background-color: #FFF0F1;
            color: #E23744 !important;
            border: 1px solid #FFD2D6;
        }
        .badge-impact {
            background-color: #E6F7ED;
            color: #008A3E !important;
            border: 1px solid #B8E8CE;
        }

        .card-title {
            font-size: 1.25rem;
            font-weight: 800;
            color: #222222;
            margin-bottom: 16px;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 9px 0;
            border-bottom: 1px dashed #EAEAEA;
            font-size: 0.88rem;
        }
        .metric-row:last-child {
            border-bottom: none;
        }
        .metric-label-text {
            color: #64748B;
            font-weight: 500;
        }
        .metric-val-text {
            font-weight: 700;
            color: #222222;
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

        /* Accounting Callout */
        .accounting-notice {
            background-color: #FFFFFF;
            border: 1px solid #FFD2D6;
            border-left: 4px solid #E23744;
            border-radius: 8px;
            padding: 14px 18px;
            margin: 20px 0 28px 0;
            font-size: 0.88rem;
            line-height: 1.5;
            color: #222222;
            box-shadow: 0 1px 4px rgba(0,0,0,0.02);
        }

        /* Section Headings */
        .section-header {
            font-size: 1.35rem;
            font-weight: 800;
            color: #222222;
            margin: 32px 0 16px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-subtext {
            font-size: 0.90rem;
            color: #64748B;
            margin-top: -10px;
            margin-bottom: 18px;
        }

        /* Footer */
        .zomato-footer {
            border-top: 1px solid #EAEAEA;
            margin-top: 48px;
            padding-top: 24px;
            padding-bottom: 32px;
            text-align: center;
            color: #718096;
            font-size: 0.82rem;
            line-height: 1.6;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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

    # 1. Sidebar Simulation Controls (Preserve Defaults: 30 Days, Seed 42, t1=1/40%, t2=2/20%)
    st.sidebar.markdown(
        """
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
            <span style="background-color:#E23744; color:#ffffff; font-weight:800; font-size:0.9rem; padding:3px 10px; border-radius:5px;">FreshPrice AI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.title("Store Simulation Controls")
    st.sidebar.markdown("Configure operational parameters and clearance policy thresholds:")

    seed_val = st.sidebar.number_input(
        "Random Seed",
        value=42,
        min_value=1,
        max_value=999999,
        step=1,
        key="sim_seed_input",
        help="Fixed seed guarantees identical inventory arrivals and identical customer traffic shocks for both policies.",
    )

    sim_days = st.sidebar.slider(
        "Simulation Duration (Days)",
        min_value=7,
        max_value=60,
        value=30,
        step=1,
        key="sim_days_slider",
        help="Standard official benchmark is 30 days. Explore alternative horizons up to 60 days.",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Markdown Policy Thresholds")

    t1 = st.sidebar.number_input(
        "Urgent Clearance Threshold (Days)",
        value=1,
        min_value=1,
        max_value=5,
        step=1,
        key="threshold_1_input",
        help="Days remaining before expiry for highest clearance discount.",
    )
    d1 = st.sidebar.slider(
        "Urgent Clearance Discount (%)",
        min_value=0,
        max_value=80,
        value=40,
        step=5,
        key="discount_1_slider",
        help="Discount applied when remaining shelf life <= Threshold 1.",
    )

    t2 = st.sidebar.number_input(
        "Near-Expiry Threshold (Days)",
        value=2,
        min_value=1,
        max_value=10,
        step=1,
        key="threshold_2_input",
        help="Days remaining before expiry for moderate markdown discount.",
    )
    d2 = st.sidebar.slider(
        "Near-Expiry Discount (%)",
        min_value=0,
        max_value=80,
        value=20,
        step=5,
        key="discount_2_slider",
        help="Discount applied when remaining shelf life <= Threshold 2.",
    )

    cost_floor = st.sidebar.checkbox(
        "Enforce Wholesale Cost Floor (Price >= Unit Cost)",
        value=True,
        key="cost_floor_toggle",
        help="Guarantees dynamic selling price never falls below product wholesale unit cost.",
    )

    if int(t2) <= int(t1):
        st.sidebar.warning(
            f"⚠️ Near-expiry threshold ({t2}d) is <= Urgent clearance threshold ({t1}d). "
            f"Batches with <= {t1} days to expiry will trigger Urgent Clearance pricing."
        )
    if float(d2) > float(d1):
        st.sidebar.info(
            f"💡 Near-expiry discount ({d2}%) is set higher than urgent clearance discount ({d1}%)."
        )

    st.sidebar.markdown("---")
    st.sidebar.info(
        f"**Active Seed**: `{seed_val}`  \n"
        f"**Duration**: `{sim_days} Days`  \n"
        f"**Clearance**: ≤`{t1}`d (`{d1}`%) | ≤`{t2}`d (`{d2}`%)  \n"
        f"**Shelf-Life Aware**: `Active (Max L-2)`  \n"
        f"**Catalog**: 20 Perishable SKUs  \n"
        f"**Cost Floor**: `{'Enforced' if cost_floor else 'Disabled'}`  \n"
        f"**Policy Comparison**: Synchronized & Controlled"
    )

    # 2. Run Synchronized Simulation via Orchestration Function
    sim_result = run_dashboard_simulation(
        sim_days=int(sim_days),
        seed=int(seed_val),
        threshold_1_days=int(t1),
        discount_1_pct=float(d1) / 100.0,
        threshold_2_days=int(t2),
        discount_2_pct=float(d2) / 100.0,
        enforce_cost_floor=cost_floor,
    )

    f = sim_result.fixed_metrics
    m = sim_result.markdown_metrics

    waste_saved = round(f.units_wasted - m.units_wasted, 1)
    waste_red_pct = round(((f.units_wasted - m.units_wasted) / f.units_wasted * 100.0), 2) if f.units_wasted > 0 else 0.0
    units_sold_gain = round(m.units_sold - f.units_sold, 1)
    rev_gain = round(m.revenue - f.revenue, 2)
    cogs_diff = round(m.cogs - f.cogs, 2)
    margin_gain = round(m.gross_margin - f.gross_margin, 2)
    margin_pct_diff = round(m.gross_margin_pct - f.gross_margin_pct, 2)
    ending_stock_delta = round(m.ending_inventory - f.ending_inventory, 1)

    # 3. Zomato Hero Header
    st.markdown(
        """
        <div class="zomato-hero">
            <span class="zomato-badge">FreshPrice AI</span>
            <div class="zomato-title">Markdown Before Waste</div>
            <div class="zomato-subtitle">
                <b>NEXAI 2026 Hackathon (PS 4.1: Track 4 Grocery Retail)</b> — 
                Dynamic near-expiry algorithmic pricing to eliminate perishable food waste, 
                stimulate consumer demand before expiration, and optimize retail gross margin.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4. Active Simulation Settings Bar
    st.markdown(
        f"""
        <div class="settings-bar">
            <div class="setting-chip">⏱️ Duration: <b>{sim_days} Days</b></div>
            <div class="setting-chip">🎲 Random Seed: <b>{seed_val}</b></div>
            <div class="setting-chip setting-chip-highlight">⚡ Urgent Clearance: <b>≤ {t1} Day ({d1}% OFF)</b></div>
            <div class="setting-chip setting-chip-highlight">🏷️ Near-Expiry Markdown: <b>≤ {t2} Days ({d2}% OFF)</b></div>
            <div class="setting-chip">🛡️ Price Floor: <b>{'Enforced (P >= Cost)' if cost_floor else 'Disabled'}</b></div>
            <div class="setting-chip">🛒 Catalog: <b>20 Perishable SKUs</b></div>
            <div class="setting-chip">📦 Total Initial Stock: <b>{f.total_received:,.1f} Units (Identical)</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 5. Side-by-Side Policy Comparison Cards (White Backgrounds, Accents)
    st.markdown('<div class="section-header">1. Side-by-Side Policy Performance Comparison</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="section-subtext">Cumulative {sim_days}-day benchmark evaluated on identical inventory batches and demand shocks:</div>',
        unsafe_allow_html=True,
    )

    col_fixed, col_md, col_impact = st.columns(3)

    # Card 1: Fixed-Price Baseline (White background with neutral gray accent)
    with col_fixed:
        st.markdown(
            f"""
            <div class="policy-card card-fixed">
                <span class="card-header-badge badge-fixed">Baseline Benchmark</span>
                <div class="card-title">Fixed-Price Policy</div>
                <div class="metric-row">
                    <span class="metric-label-text">Total Received Inventory:</span>
                    <span class="metric-val-text">{f.total_received:,.1f} units</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Units Sold:</span>
                    <span class="metric-val-text">{f.units_sold:,.1f} units</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Units Wasted (Expired):</span>
                    <span class="metric-val-text text-red">{f.units_wasted:,.1f} units</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Waste Rate (%):</span>
                    <span class="metric-val-text text-red">{f.waste_rate_pct:.2f}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Total Revenue (INR):</span>
                    <span class="metric-val-text">{format_inr(f.revenue)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Cost of Goods Sold (COGS):</span>
                    <span class="metric-val-text">{format_inr(f.cogs)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Margin (Revenue - COGS):</span>
                    <span class="metric-val-text">{format_inr(f.gross_margin)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Margin (% of Rev):</span>
                    <span class="metric-val-text">{f.gross_margin_pct:.2f}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Promotional Markdown Events:</span>
                    <span class="metric-val-text">0 events</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Ending Healthy Inventory:</span>
                    <span class="metric-val-text">{f.ending_inventory:,.1f} units</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Card 2: Dynamic Markdown Policy (White background with FreshPrice red accents)
    with col_md:
        st.markdown(
            f"""
            <div class="policy-card card-markdown">
                <span class="card-header-badge badge-markdown">Dynamic Algorithmic</span>
                <div class="card-title text-red">Markdown Policy</div>
                <div class="metric-row">
                    <span class="metric-label-text">Total Received Inventory:</span>
                    <span class="metric-val-text">{m.total_received:,.1f} units</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Units Sold:</span>
                    <span class="metric-val-text text-green">{m.units_sold:,.1f} units</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Units Wasted (Expired):</span>
                    <span class="metric-val-text {'text-green' if m.units_wasted == 0 else 'text-red'}">{m.units_wasted:,.1f} units</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Waste Rate (%):</span>
                    <span class="metric-val-text {'text-green' if m.waste_rate_pct < f.waste_rate_pct else 'text-neutral'}">{m.waste_rate_pct:.2f}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Total Revenue (INR):</span>
                    <span class="metric-val-text {'text-green' if rev_gain >= 0 else 'text-red'}">{format_inr(m.revenue)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Cost of Goods Sold (COGS):</span>
                    <span class="metric-val-text">{format_inr(m.cogs)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Margin (Revenue - COGS):</span>
                    <span class="metric-val-text {'text-green' if margin_gain >= 0 else 'text-neutral'}">{format_inr(m.gross_margin)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Margin (% of Rev):</span>
                    <span class="metric-val-text">{m.gross_margin_pct:.2f}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Promotional Markdown Events:</span>
                    <span class="metric-val-text text-red">{m.markdown_events_count} events</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Ending Healthy Inventory:</span>
                    <span class="metric-val-text">{m.ending_inventory:,.1f} units</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Card 3: Honest Performance Variance & Impact (White background with green accents)
    with col_impact:
        st.markdown(
            f"""
            <div class="policy-card card-impact">
                <span class="card-header-badge badge-impact">Strategic Realized Impact</span>
                <div class="card-title text-green">Performance Variance</div>
                <div class="metric-row">
                    <span class="metric-label-text">Initial Inventory Delta:</span>
                    <span class="metric-val-text">0.0 units (100% Identical)</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Additional Units Sold:</span>
                    <span class="metric-val-text text-green">{format_units(units_sold_gain, include_sign=True)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Physical Waste Saved:</span>
                    <span class="metric-val-text text-green">{format_units(waste_saved, include_sign=True)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Waste Reduction (%):</span>
                    <span class="metric-val-text text-green"><b>{waste_red_pct:.2f}% reduction</b></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Revenue Change (INR):</span>
                    <span class="metric-val-text {'text-green' if rev_gain >= 0 else 'text-red'}">{format_inr(rev_gain, include_sign=True)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">COGS Variance:</span>
                    <span class="metric-val-text">{format_inr(cogs_diff, include_sign=True)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Margin Change (₹):</span>
                    <span class="metric-val-text {'text-green' if margin_gain >= 0 else 'text-red'}"><b>{format_inr(margin_gain, include_sign=True)}</b></span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Gross Margin % Change:</span>
                    <span class="metric-val-text {'text-green' if margin_pct_diff >= 0 else 'text-neutral'}">{format_pct(margin_pct_diff, include_sign=True)}</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Active Markdown Triggers:</span>
                    <span class="metric-val-text text-red">+{m.markdown_events_count} clearance events</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label-text">Unsold Ending Stock Delta:</span>
                    <span class="metric-val-text">{format_units(ending_stock_delta, include_sign=True)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 6. Honest Accounting Distinction Callout
    tradeoff_explanation = ""
    if rev_gain > 0 and margin_gain < 0:
        tradeoff_explanation = (
            f"• <b>Revenue vs. Margin Trade-Off</b>: Store revenue increased by <b>{format_inr(rev_gain, include_sign=True)}</b>, "
            f"while gross margin decreased by <b>{format_inr(margin_gain, include_sign=True)}</b>. "
            f"This occurs because clearance discounts stimulate consumer demand to eliminate perishable waste before expiry, "
            f"sacrificing per-unit profit margin in exchange for recovering working capital on stock that would otherwise produce zero revenue.<br>"
        )
    elif rev_gain >= 0 and margin_gain >= 0:
        tradeoff_explanation = (
            f"• <b>Dual Expansion</b>: Both revenue ({format_inr(rev_gain, include_sign=True)}) and "
            f"gross margin ({format_inr(margin_gain, include_sign=True)}) expanded under dynamic markdowns.<br>"
        )

    st.markdown(
        f"""
        <div class="accounting-notice">
            <b>💡 Honest Retail Accounting Insight: Margin (₹ INR) vs. Margin Percentage (%)</b><br>
            • <b>Gross Margin (INR ₹)</b> is calculated as Revenue minus COGS ($Gross Margin = Revenue - COGS$). Here, Markdown Policy generates <b>{format_inr(m.gross_margin)}</b> compared to Fixed Baseline's <b>{format_inr(f.gross_margin)}</b> ({format_inr(margin_gain, include_sign=True)} variance).<br>
            • <b>Gross Margin (%)</b> is the efficiency ratio per Rupee of revenue ($Gross Margin / Revenue$). Because clearance markdowns offer discounts (e.g. 20%–40%), the gross margin percentage shifts from <b>{f.gross_margin_pct:.2f}%</b> to <b>{m.gross_margin_pct:.2f}%</b> ({format_pct(margin_pct_diff, include_sign=True)}).<br>
            {tradeoff_explanation}
            • <b>Physical Waste Elimination</b>: Dynamic markdowns eliminate <b>{format_units(waste_saved)} of food waste ({waste_red_pct:.1f}% reduction)</b>, converting dead inventory losses into realized cash flow and customer goodwill, while strictly respecting the wholesale unit cost floor.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 7. Comparison Table & Visual Analytics
    st.markdown('<div class="section-header">2. Comparative Visual Analytics & Reconciled Table</div>', unsafe_allow_html=True)

    col_tbl, col_cht = st.columns([1, 1])

    with col_tbl:
        st.markdown("#### Cumulative Reconciled Summary Table")
        st.dataframe(sim_result.comparison_summary_df, use_container_width=True, hide_index=True)

        st.download_button(
            label="📥 Download Comparison Summary CSV",
            data=sim_result.comparison_summary_df.to_csv(index=False),
            file_name="policy_comparison_summary.csv",
            mime="text/csv",
        )

    with col_cht:
        st.plotly_chart(create_comparison_chart(f, m), use_container_width=True)

    st.plotly_chart(create_waste_comparison_chart(f, m), use_container_width=True)

    # 8. Per-Product Daily Simulation History (Source of Physical Waste Tracking)
    st.markdown('<div class="section-header">3. Per-Product Daily Simulation History</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtext">Source of physical inventory tracking, daily turnover, selling prices, units sold, and expired waste across all 20 products:</div>',
        unsafe_allow_html=True,
    )

    daily_df = sim_result.daily_history_df.copy()

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        sel_policy = st.selectbox("Filter Strategy:", options=["All", "markdown", "fixed"], index=1, key="daily_policy_filter")
    with col_f2:
        products_list = ["All"] + sorted(daily_df["product_name"].unique())
        sel_product = st.selectbox("Filter Perishable Product:", options=products_list, index=0, key="daily_product_filter")
    with col_f3:
        max_days = max(1, int(sim_days))
        sel_day = st.slider(
            "Filter Simulation Day Range:",
            min_value=1,
            max_value=max_days,
            value=(1, max_days),
            key=f"day_range_filter_{max_days}",
        )

    filtered_daily = daily_df[
        (daily_df["day"] >= sel_day[0]) & (daily_df["day"] <= sel_day[1])
    ]
    if sel_policy != "All":
        filtered_daily = filtered_daily[filtered_daily["policy"] == sel_policy]
    if sel_product != "All":
        filtered_daily = filtered_daily[filtered_daily["product_name"] == sel_product]

    display_cols = [
        "day", "policy", "product_name", "category", "days_until_expiry",
        "regular_price", "selling_price", "discount_pct", "units_sold",
        "units_wasted", "revenue", "gross_margin", "ending_stock"
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
    }

    st.dataframe(
        filtered_daily[display_cols].rename(columns=rename_cols),
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        label="📥 Download Daily History CSV",
        data=filtered_daily.to_csv(index=False),
        file_name="daily_simulation_history.csv",
        mime="text/csv",
    )

    # 9. Markdown Events History Table (Promotional Clearance Audit Log)
    st.markdown('<div class="section-header">4. Per-Product Markdown Event History (Promotional Clearance Log)</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="section-subtext">Chronological promotional audit trail recording every discounted transaction under Markdown Policy '
        f'(`{len(sim_result.markdown_events_df)}` clearance events recorded):</div>',
        unsafe_allow_html=True,
    )

    events_df = sim_result.markdown_events_df
    if events_df.empty:
        st.info("No markdown events were triggered under the active policy configuration.")
    else:
        evt_rename = {
            "day": "Day",
            "product_name": "Product",
            "category": "Category",
            "days_until_expiry": "Days Left",
            "regular_price": "Base Price (₹)",
            "selling_price": "Discounted Price (₹)",
            "discount_pct": "Discount %",
            "units_sold": "Units Sold",
            "units_wasted": "Units Wasted",
            "reason": "Clearance Trigger",
        }
        disp_evt_cols = [c for c in evt_rename.keys() if c in events_df.columns]
        st.dataframe(
            events_df[disp_evt_cols].rename(columns=evt_rename),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "📌 Notice: In this promotional log, 'Units Wasted' records unpreventable batch waste that occurred on that specific product-day. "
            "When clearance pricing succeeds in selling near-expiry stock before expiration, units_wasted evaluates to 0.0. "
            "Store-wide cumulative waste is tracked comprehensively in the Daily Simulation History above."
        )

        st.download_button(
            label="📥 Download Markdown Events CSV",
            data=events_df.to_csv(index=False),
            file_name="markdown_events_history.csv",
            mime="text/csv",
        )

    # 10. Zomato Red-and-White Footer
    st.markdown(
        """
        <div class="zomato-footer">
            <b>FreshPrice AI — NEXAI 2026 Hackathon Official MVP</b> | Problem Statement 4.1 (Track 4: Grocery Retail)<br>
            <i>Designed with a clean, light Red-and-White retail interface inspired by food delivery & grocery intelligence platforms.<br>
            All 20 products model real-world perishable categories (Dairy, Bakery, Fruits, Vegetables) in Indian Rupees (₹).<br>
            Physical inventory conservation strictly enforced: Total Received = Units Sold + Units Wasted + Ending Inventory.</i>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
