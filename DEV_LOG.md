# FreshPrice - Development Log

## Milestone 3.1: Output File Lock & PermissionError Handling Fix
- **Date**: 2026-10-22
- **Status**: Completed & Verified.
- **Problem**:
  - `PermissionError: [Errno 13] Permission denied: 'C:\freshprice\data\category_performance_summary.csv'` occurred when writing CSV outputs while open/locked in applications such as Microsoft Excel.
- **Components Updated**:
  - `src/performance_analysis.py`:
    - Implemented `save_dataframe_to_csv(df, target_path)`:
      - Validates and creates parent directories automatically via `path.parent.mkdir(parents=True, exist_ok=True)`.
      - Catches `PermissionError` and raises a clear, actionable exception explaining that the file is locked by Excel/spreadsheet viewers and instructing the user to close the file and rerun.
      - Never silently ignores write failures or reports false success.
      - Does not delete existing output files automatically.
    - Updated `generate_markdown_report` and `generate_charts` with equivalent actionable error handling.
    - Enhanced `main()` CLI entrypoint to catch `PermissionError` cleanly and print actionable guidance to `sys.stderr` with exit code 1.
  - `tests/test_performance_analysis.py`:
    - Added `test_save_dataframe_to_csv_creates_missing_directory`: Verifies missing parent directory creation.
    - Added `test_save_dataframe_to_csv_permission_error_handling`: Verifies clear, user-friendly exception messaging when file writing is blocked.
    - Added `test_run_phase3_analysis_permission_error_propagation`: Verifies errors propagate without silent suppression.
- **Verification**:
  - 36/36 tests passed cleanly via `py -m pytest tests -v`.

## Milestone 3.2: Phase 3 Sensitivity Analysis Audit & Inelastic Safeguard Verification
- **Date**: 2026-10-22
- **Status**: Completed & Verified.
- **Audit Findings**:
  1. **Discount Cap Plateau (30% vs 35%)**:
     - 30% and 35% discount caps yield identical outputs (38.42 unsold units, 0.68% waste rate, ₹107,491.34 net profit).
     - Verified that the wholesale price floor ($P \\ge \\text{unit\\_cost}$) restricts maximum allowable discounts to $\\le 24.22\\%$ across all batches (specifically `PROD-0042 Garlic Herb Baguette`).
     - Within the feasible margin range $[0, 24.22\\%]$, the optimal profit-maximizing markdown is 22.63% (selling at ₹51.36 yields ₹1,032.34 revenue vs ₹1,031.15 at the ₹50.30 cost floor).
     - Because no batch in the 120-item dataset can legally or profitably utilize a discount $\\ge 30\\%$, caps beyond 30% are non-binding.
  2. **Elasticity Scenarios (|Ed| = 0.5 and 1.0 Matching Fixed Baseline)**:
     - Verified that $|E_d| = 0.5$ (inelastic) and $|E_d| = 1.0$ (unitary elastic) produce outputs identical to fixed pricing (60.60 unsold units, 1.08% waste rate, ₹107,319.73 net profit).
     - In microeconomics, reducing prices under inelastic demand strictly reduces total revenue ($\\Delta R < 0$). Under unitary elasticity, linear price reduction yields $(1-d^2) < 1$, reducing revenue on sold units.
     - The pricing engine's profitability rule (`cand_profit > best_profit + 0.05`) detects that discounting under $|E_d| \\le 1.0$ erodes net retail profit and protects margin by retaining regular prices.
  3. **Zero Waste in Produce and Packaged Food**:
     - Verified that coverage ratios ($S_0 / (D \\times T)$) for Fruits ($\\le 0.61$), Vegetables ($\\le 0.69$), and Packaged Food ($\\approx 0.015$) indicate baseline demand clears 100% of batch inventory before expiry.
     - Retaining regular prices is optimal; discounting items that naturally sell out would dilute profits without increasing volume.
  4. **Accounting & Reconciliation**:
     - Reconciled physical inventory conservation ($5,621.00$ units) and initial inventory cost ($₹355,862.73$) with zero variance ($0.0000$) across all summary tables.
- **Components Updated**:
  - `src/performance_analysis.py`:
    - Expanded `generate_markdown_report` with Section 2.1 (Category Spoilage Dynamics & Produce Turnover), Section 3.1 (Discount Plateau Trace), Section 4.1 (Microeconomic Trace of Elasticity), and Section 5.1 (Accounting Reconciliation Audit).
  - `reports/phase3_performance_report.md`:
    - Regenerated with comprehensive audit explanations, microeconomic proofs, and reconciliation verifications.
  - `tests/test_performance_analysis.py`:
    - Added `test_discount_sensitivity_plateau_and_constraints`: Verifies 30% and 35% equivalence, price floor enforcement, and discount cap adherence.
    - Added `test_elasticity_sensitivity_inelastic_safeguard`: Verifies $|E_d| \\le 1.0$ holds regular prices and matches fixed baseline.
    - Added `test_sensitivity_physical_inventory_and_cost_reconciliation`: Verifies inventory conservation and cost reconciliation across all sensitivity rows.
    - Added `test_category_and_aggregate_reconciliation`: Verifies exact mathematical alignment between category totals and aggregate summary tables.
- **Verification**:
  - 40/40 tests passed cleanly via `py -m pytest tests -v`.

## Milestone 4.1: Phase 4 Streamlit Interactive Dashboard Implementation
- **Date**: 2026-10-22
- **Status**: Completed & Verified.
- **Implemented Features**:
  1. **Dashboard Architecture (`src/dashboard.py` & `app.py`)**:
     - Built multi-page retail analytics dashboard using **Streamlit** and **Plotly**.
     - Configured title "FreshPrice AI" and subtitle "AI-Assisted Markdown Pricing to Reduce Grocery Waste".
     - Injected custom CSS for modern card metrics and readable typography.
     - Formatted all monetary values in INR (`₹`) and percentage deltas.
     - Added standard disclaimer footer affirming synthetic academic simulation status.
     - Enabled dual execution: `streamlit run app.py` and `streamlit run src/dashboard.py`.
  2. **Page 1: Executive Overview**:
     - Reconciled KPI cards: Total Initial Inventory (5,621 units), Fixed Waste Rate (1.08%), Dynamic Waste Rate (0.68%), Waste Reduction (36.60%), Fixed Net Profit (₹107,319.73), Dynamic Net Profit (₹107,491.34), and Net Profit Gain (+₹171.61).
     - Plotly grouped bar chart contrasting Revenue, Waste Loss, and Net Retail Profit.
     - Interactive GAAP retail accounting reconciliation accordion verifying zero variance.
  3. **Page 2: Category Insights**:
     - Department-level performance across Dairy, Bakery, Fruits, Vegetables, and Packaged Food.
     - Three Plotly charts: Waste Rate (%) by Category, Net Retail Profit (₹) by Category, and Unsold Spoilage Volume (Units) by Category.
     - Sortable Category Summary Table with formatted revenue, profit, and waste reduction columns.
     - Contextual retail dynamics guidance explaining category turnover and perishability differences.
  4. **Page 3: Discount Simulator**:
     - Interactive Streamlit slider (0% to 35% maximum discount cap).
     - Dynamic recalculation powered directly by existing pricing engine (`PricingPolicyConfig` and `simulate_inventory`).
     - Comparative metric cards (units sold, waste units, waste rate, revenue, net profit difference).
     - Pricing Decision Audit panel breaking down batches discounted, regular prices held, and limitation reasons.
     - Batch-level inspection table with filters (Discounted batches, Waste batches, All 120 batches).
     - Transparency alert explaining the 30% vs 35% non-binding discount plateau and price floor constraint.
  5. **CSV Export Capabilities**:
     - Added one-click Streamlit `st.download_button` options on Page 1 (`executive_overview_summary.csv`), Page 2 (`category_performance_summary.csv`), and Page 3 (`batch_simulation_results_<cap>pct_cap.csv` and filtered audit table).
     - Implemented `export_simulation_to_csv` function in `src/dashboard.py`.
     - Generated and saved `data/batch_simulation_results.csv` (120 batches) and `data/executive_kpis_summary.csv` directly to disk.
  6. **Dependencies & Test Suite**:
     - Updated `requirements.txt` with `streamlit>=1.30.0` and `plotly>=5.18.0`.
     - Created `tests/test_dashboard.py` with 11 comprehensive tests validating data loading, KPI calculations, dynamic simulation reactivity, price floor enforcement, Plotly chart generation, and CSV export functionality.
- **Verification**:
  - 51/51 tests passed cleanly via `py -m pytest tests -v`.

## Milestone 5.0: NEXAI 2026 Official MVP Simplification (PS 4.1: Markdown Before Waste)
- **Date**: 2026-10-22
- **Status**: Completed & Verified.
- **Problem Statement Alignment**:
  - Simplified the project to strictly satisfy the 10 mandatory requirements of the official NEXAI 2026 Hackathon Problem Statement 4.1 (Track 4: Grocery Retail).
- **Core Simulator (`src/store_simulator.py`)**:
  - Implemented 30-day dynamic store simulator with 20 perishable products across 4 categories (Dairy, Bakery, Fruits, Vegetables).
  - Modeled batch arrivals with arrival dates, expiry dates, and FEFO (First-Expiry-First-Out) fulfillment.
  - Implemented strict expiry rule: no product is sold on or after expiry day ($t \ge \text{expiry\_day}$).
  - Demand generation responds dynamically to base demand draws, price discounts ($\eta = 1.3\text{--}1.9$), and clearance display visibility.
  - Synchronized twin simulation loop: Fixed-Price Baseline vs Markdown Policy with identical batch arrivals, identical baseline demand shocks, and identical starting conditions via controlled random seed.
  - Configurable near-expiry thresholds ($T_1, T_2$) and discount percentages ($d_1, d_2$) with wholesale cost floor protection ($P \ge \text{unit\_cost}$).
  - Reconciled standard GAAP metrics: Units Received, Sold, Wasted, Waste Rate %, Revenue, COGS, Gross Margin, and Gross Margin %.
- **Single-Page Dashboard (`src/dashboard.py`)**:
  - Simplified into ONE unified Streamlit dashboard:
    1. Sidebar controls: Random seed, 30-day duration, clearance thresholds ($T_1, T_2$), discount percentages ($d_1, d_2$), and cost floor toggle.
    2. Main comparison: KPI cards for units sold, units wasted, waste rate %, revenue, COGS, gross margin, and margin %.
    3. Plotly visual comparison charts for financial metrics (Revenue & Gross Margin) and physical waste units.
    4. Per-product daily simulation history with interactive filters (policy, product, day range).
    5. Markdown event audit table detailing every discounted product, day, price cut, and clearance trigger.
    6. CSV export buttons for all core MVP deliverables.
- **Test Suite (`tests/test_store_simulator.py` & `tests/test_dashboard.py`)**:
  - Added 15 comprehensive unit tests in `test_store_simulator.py` validating 20 products, 30 days, batch arrivals, FEFO fulfillment, no sales after expiry, inventory conservation, cost floors, identical starting conditions, seed reproducibility, stochastic divergence across seeds, accounting identities, and markdown event recording.
  - Total test suite now at 59 passing tests.
- **Verification**:
  - 59/59 tests passed cleanly via `py -m pytest tests -v`.

## Milestone 5.1: Zomato Red-and-White Dashboard Redesign & Root-Cause Audit
- **Date**: 2026-10-22
- **Status**: Completed & Verified.
- **Root-Cause Investigation & Resolution**:
  - Investigated observations in `markdown_events_history.csv` (580 records across Days 1–34 with `units_wasted = 0`).
  - Identified exact root cause: file was generated from a sensitivity run with parameters `sim_days=34`, `seed=100`, `threshold_2_days=6`, `discount_2_pct=0.20`.
  - Clarified that `units_wasted = 0` in markdown event records indicates near-expiry markdowns successfully stimulated consumer demand before product expiry, preventing morning disposal dumps.
  - Documented that store-wide cumulative waste is tracked comprehensively in `daily_simulation_history.csv` (and `policy_comparison_summary.csv`), not inferred solely from the promotional markdown audit log.
- **Zomato Red-and-White Interface Redesign (`src/dashboard.py`)**:
  - Designed clean, high-contrast Red-and-White retail interface inspired by modern food delivery and grocery platforms (Zomato brand palette: `#E23744`, `#FFF5F6`, `#1C1C1C`, `#008A3E`).
  - Hero header with custom branding, hackathon track badge, and tagline.
  - Active Settings Bar rendering live visual chips for simulation duration, seed, urgent/near-expiry clearance thresholds & discounts, wholesale cost floor status, and catalog SKU count.
  - Side-by-side policy performance comparison cards:
    1. **Fixed-Price Policy (Baseline Benchmark)**: Slate card showing full-price performance, 1,617.0 wasted units, and baseline gross margin.
    2. **Markdown Policy (Dynamic Algorithmic)**: Zomato Red card displaying dynamic pricing outcomes, 100% waste elimination, and expanded sales.
    3. **Performance Variance (Realized Impact)**: Emerald card showing exact deltas for units sold, waste units saved (-1,617.0), revenue growth (+₹57,931), gross margin change, and gross margin percentage change.
  - Honest accounting callout distinguishing Gross Margin (INR ₹ contribution) from Gross Margin (% revenue efficiency).
  - Themed Plotly charts for financial metrics (Total Revenue & Gross Margin) and physical waste units.
  - Distinct tables and download buttons for daily simulation history (physical waste source) and markdown events (promotional clearance log).
- **Verification**:
  - All mathematical formulas, seed reproducibility, and simulation metrics remain 100% identical.
  - 59/59 tests passed cleanly via `py -m pytest tests -v`.

## Milestone 5.2: Strict Light Theme Configuration (.streamlit/config.toml & UI Update)
- **Date**: 2026-10-22
- **Status**: Completed & Verified.
- **Theme Configuration (`.streamlit/config.toml`)**:
  - Configured Streamlit light theme specification:
    ```toml
    [theme]
    base = "light"
    primaryColor = "#E23744"
    backgroundColor = "#FFFFFF"
    secondaryBackgroundColor = "#F8F8F8"
    textColor = "#222222"
    font = "sans serif"
    ```
- **Light Theme UI Adjustments (`src/dashboard.py`)**:
  - Main application canvas strictly set to pure white (`#FFFFFF`).
  - Sidebar background strictly set to soft light gray (`#F8F8F8`) with neutral border `#EAEAEA`.
  - Body and heading text colors enforced to dark charcoal (`#222222`).
  - Policy cards: white backgrounds (`#FFFFFF`) with subtle light-gray borders (`#E8E8E8`) and soft shadows:
    - Fixed-Price Card: Neutral gray accent (`#718096`).
    - Dynamic Markdown Card: FreshPrice red accent (`#E23744`).
    - Performance Variance Card: Green accent (`#008A3E`).
  - Plotly charts updated with explicit white paper/plot backgrounds (`#FFFFFF`), light gridlines (`#F0F0F0`), and dark charcoal labels (`#222222`).
  - Form widgets, inputs, selectboxes, dataframes, and buttons styled with light contrast and red hover effects.
- **Verification**:
  - 59/59 tests passed cleanly via `py -m pytest tests -v`.

## Milestone 5.3: Fix Simulation Reactive Triggers & Widget Orchestration
- **Date**: 2026-10-22
- **Status**: Completed & Verified.
- **Root-Cause Investigation**:
  - Identified why sidebar markdown discount changes previously failed to update displayed results:
    1. **Widget bound crash**: `d2` slider was defined with dynamic `max_value=int(d1)` and default `value=20`. When `d1` was lowered below 20% (e.g. 10%), Streamlit raised an uncaught `StreamlitAPIException` (`value 20 > max_value 10`), terminating execution before `run_store_simulation` ran.
    2. **Threshold bound crash**: `t2` was defined with `min_value=int(t1) + 1` and `value=2`. If `t1` was set to 2, `value 2 < min_value 3` crashed the run.
    3. **Day range filter crash**: `sel_day` slider retained stale upper bounds if `sim_days` was reduced.
    4. **Wholesale cost floor plateau**: For `d1 >= 37%`, prices were constrained by the unit cost floor, producing identical figures unless $d_1$ dropped below 37%.
- **Solution & Orchestration Refactor (`src/dashboard.py`)**:
  - Created standalone simulation orchestration function `run_dashboard_simulation()` decoupled from Streamlit rendering.
  - Decoupled `d1` and `d2` sliders (`0% to 80%` with step 5) and assigned explicit widget keys (`discount_1_slider`, `discount_2_slider`).
  - Added gentle non-blocking sidebar notifications for inverted thresholds or discounts (`t2 <= t1` or `d2 > d1`).
  - Assigned dynamic keys to day range filter (`f"day_range_filter_{max_days}"`).
- **Regression Test Suite (`tests/test_dashboard.py`)**:
  - Added 8 comprehensive regression tests validating discount reactivity, threshold changes, seed/duration recalculation, latest-result display, fixed baseline independence, deterministic reproducibility, and GAAP accounting/inventory conservation.
  - Total test suite expanded to 67 passing tests.
- **Verification**:
  - Verified manual discount change from 40% to 10% recalculates results (`units_sold: 14825.9 -> 14820.7, margin: ₹157,170.84 -> ₹159,302.30`), and restoring returns identical baseline.
  - 67/67 tests passed cleanly via `py -m pytest tests -v`.
