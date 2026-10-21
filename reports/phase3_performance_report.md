# FreshPrice AI - Phase 3: Performance Evaluation & Sensitivity Analysis Report

**Project**: FreshPrice AI - Markdown Before Waste  
**Repository**: [https://github.com/thilagars4767-ux/freshprice-ai](https://github.com/thilagars4767-ux/freshprice-ai)  
**Currency**: All monetary values are in INR (Indian Rupees - ₹).  
**Data Status**: Purely synthetic simulation data for academic and hackathon evaluation.

---

## 1. Executive Summary & Key Findings

1. **Greatest Waste Reduction by Category**:
   - **Bakery** achieved the largest percentage waste reduction (**80.21%** reduction, cutting spoilage from 9.60 down to 1.90 loaves).
   - **Dairy** achieved the largest absolute volume of waste rescued (**14.48 units saved**, a **28.39%** reduction).
   - **Fruits, Vegetables, and Packaged Food** registered 0.00% waste under both strategies because baseline demand clears stock within shelf-life.
2. **Net Retail Profit Improvement**:
   - Dynamic markdown strictly **improved Net Retail Profit** in all categories exhibiting inventory surplus (+₹116.12 in Bakery, +₹55.49 in Dairy).
   - In zero-waste categories, profit remained identical between strategies with zero margin dilution because the pricing engine held regular prices.
3. **Maximum Discount Setting Behavior**:
   - Waste reduction and profit improve steadily as the cap increases from **10%** (31.35% waste reduction) to **30%** (36.60% waste reduction).
   - Performance **plateaus beyond 30%** (35% yields identical results) because the highest clearance discount needed in the current catalog is 22.6%, and wholesale cost floors prevent deeper discounting.
4. **Price-Elasticity Sensitivity Insights**:
   - **Inelastic Scenarios (|Ed| = 0.5 and 1.0)**: The engine's profitability safeguard prevented discounting, holding regular prices to avoid loss-making volume sacrifice (0% waste reduction, 0 profit loss).
   - **Elastic Scenarios (|Ed| = 1.5 and 2.0)**: Dynamic markdowns eliminated **77.00%** and **92.48%** of waste respectively, generating **+₹656.92** and **+₹1,382.11** in profit gains.
5. **Trade-Offs**:
   - While Gross Profit on sold units decreases under discounts due to reduced unit margins, Waste Loss decreases by a larger amount, resulting in a net profit gain.

---

## 2. Feature 1: Category-Level Performance Evaluation

| Category | Batches | Initial Stock | Fixed Sold | Dyn Sold | Fixed Waste | Dyn Waste | Fixed Waste % | Dyn Waste % | Waste Red % | Fixed Net Profit (INR) | Dyn Net Profit (INR) | Profit Diff (INR) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Bakery | 24 | 821 | 811.4 | 819.1 | 9.6 | 1.9 | 1.17% | 0.23% | 80.21% | ₹10,753.76 | ₹10,869.88 | +₹116.12 |
| Dairy | 24 | 1163 | 1112.0 | 1126.5 | 51.0 | 36.5 | 4.39% | 3.14% | 28.39% | ₹13,664.84 | ₹13,720.33 | +₹55.49 |
| Fruits | 24 | 999 | 999.0 | 999.0 | 0.0 | 0.0 | 0.00% | 0.00% | 0.00% | ₹33,417.11 | ₹33,417.11 | +₹0.00 |
| Packaged Food | 24 | 1094 | 1094.0 | 1094.0 | 0.0 | 0.0 | 0.00% | 0.00% | 0.00% | ₹30,804.32 | ₹30,804.32 | +₹0.00 |
| Vegetables | 24 | 1544 | 1544.0 | 1544.0 | 0.0 | 0.0 | 0.00% | 0.00% | 0.00% | ₹18,679.70 | ₹18,679.70 | +₹0.00 |

---

### 2.1 Category Spoilage Dynamics & Produce Turnover Audit

A critical question raised in performance review is why **Fruits, Vegetables, and Packaged Food** show 0.00% waste under both fixed and dynamic pricing:

1. **Packaged Food (Realistic Non-Perishability)**:
   - Items in this category (Basmati Rice, Atta, Toor Dal, Sunflower Oil, Iodized Salt, Peanut Butter) possess long shelf lives (90 to 180 days).
   - In contrast, average batch inventory is 45.6 units against a baseline demand velocity of 25.9 units/day.
   - Cumulative demand over shelf life averages **3,462 units**, yielding an inventory coverage ratio of $\approx 0.015$ (less than 2% of cumulative demand).
   - In actual retail supermarkets, dry packaged groceries experience negligible spoilage during normal operations (<0.5%). The simulation accurately mirrors this real-world characteristic.

2. **Fresh Produce (Fruits and Vegetables Velocity)**:
   - In the synthetic dataset, daily demand rates for fresh produce reflect store-wide daily velocities (15 to 75 units/day), while initial stock represents single batch sizes (20 to 134 units) with remaining shelf lives of 4 to 24 days.
   - Consequently, cumulative expected demand ($D \times T$) ranges from 72 to 1,732 units, resulting in coverage ratios $\le 0.61$ for Fruits and $\le 0.69$ for Vegetables across all batches.
   - Because baseline demand clears all available batch stock prior to expiration, **no spoilage occurs under fixed pricing**.
   - The pricing engine correctly identifies that full inventory sells at regular price and therefore retains the regular price. Discounting items that are already on track to sell out at full price would dilute profit margin without increasing sales volume (since unconstrained demand cannot sell more than the initial physical stock).

---

## 3. Feature 2: Maximum-Discount Sensitivity Analysis

| Discount Cap | Expected Units Sold | Unsold Units (Waste) | Waste Rate (%) | Waste Red. vs Fixed (%) | Total Revenue (INR) | Gross Profit (INR) | Waste Loss (INR) | Net Retail Profit (INR) | Profit Diff vs Fixed (INR) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Fixed (0%) | 5560.40 | 60.60 | 1.08% | 0.00% | ₹463,182.46 | ₹110,639.35 | ₹3,319.62 | ₹107,319.73 | +0.00 |
| 10% | 5579.40 | 41.60 | 0.74% | 31.35% | ₹463,332.53 | ₹109,765.74 | ₹2,295.94 | ₹107,469.80 | +150.07 |
| 20% | 5581.92 | 39.08 | 0.70% | 35.51% | ₹463,353.99 | ₹109,660.45 | ₹2,169.19 | ₹107,491.26 | +171.53 |
| 30% | 5582.58 | 38.42 | 0.68% | 36.60% | ₹463,354.07 | ₹109,627.33 | ₹2,135.99 | ₹107,491.34 | +171.61 |
| 35% | 5582.58 | 38.42 | 0.68% | 36.60% | ₹463,354.07 | ₹109,627.33 | ₹2,135.99 | ₹107,491.34 | +171.61 |

---

### 3.1 Trace of Discount Sensitivity Plateau (Why 30% and 35% Yield Identical Results)

The sensitivity summary reveals that relaxing the maximum discount cap from **30% to 35%** produces 100% identical outcomes across all financial and inventory metrics:
- Expected Units Sold: **5,582.58**
- Unsold Inventory: **38.42 units** (0.68% waste rate)
- Net Retail Profit: **₹107,491.34** (+₹171.61 vs fixed baseline)

**Root-Cause Investigation & Constraints Audit**:
1. **Price Floor Constraint ($P \ge \text{unit\_cost}$)**:
   - The pricing engine enforces a strict wholesale cost boundary: `min_allowable_price = unit_cost`.
   - The maximum margin discount allowed before breaching this floor is $d_{\text{margin}} = \frac{\text{regular\_price} - \text{unit\_cost}}{\text{regular\_price}}$.
   - The effective cap is computed as `effective_max_discount = min(config.max_discount, max_margin_discount)`.
2. **Catalog Margin Profile**:
   - Across the 6 surplus batches in the 120-item inventory (in Bakery and Dairy), retail markups over wholesale cost range between 14% and 35%.
   - In Dairy (Toned Milk, Full Cream Milk), gross margins are only 13.6% to 14.6%, so discounts beyond 14.6% are illegal under the price floor constraint regardless of the cap setting.
   - In Bakery, the highest-surplus item is `PROD-0042 Garlic Herb Baguette` (regular price ₹66.38, unit cost ₹50.30), which has a maximum margin discount of **24.22%**. Any discount above 24.22% would price the baguette below its ₹50.30 cost floor.
3. **Diminishing Marginal Revenue & Profit Maximization**:
   - At a 22.63% discount (selling price ₹51.36), PROD-0042 sells 20.10 units, generating revenue of ₹1,032.34 and net profit of -₹74.26 (cutting spoilage loss by more than half from -₹150.73).
   - If discounted further to the cost floor of ₹50.30 (a 24.22% discount), expected sales rise slightly to 20.50 units, but revenue drops to ₹1,031.15, resulting in a worse net profit of -₹75.45.
   - The pricing engine's optimization rule (`cand_profit > best_profit + 0.05`) correctly selects 22.63% as the optimal markdown.
4. **Conclusion**:
   - Because no batch in the inventory can legally or profitably utilize a discount higher than 22.63%, any cap setting $\ge 30\%$ is a **non-binding constraint**.
   - Relaxing the cap from 30% to 35% (or 40%) therefore leaves decisions completely unchanged.

---

## 4. Feature 3: Price-Elasticity Sensitivity Analysis

Assumed customer sensitivity scenarios across identical inventory batches:

| Assumed Elasticity (|Ed|) | Scenario Label | Expected Units Sold | Unsold Units (Waste) | Waste Rate (%) | Waste Red. vs Fixed (%) | Total Revenue (INR) | Waste Loss (INR) | Net Retail Profit (INR) | Profit Diff vs Fixed (INR) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 0.5 | 0.5 (Inelastic) | 5560.40 | 60.60 | 1.08% | 0.00% | ₹463,182.46 | ₹3,319.62 | ₹107,319.73 | +0.00 |
| 1.0 | 1.0 (Unitary Elastic) | 5560.40 | 60.60 | 1.08% | 0.00% | ₹463,182.46 | ₹3,319.62 | ₹107,319.73 | +0.00 |
| 1.5 | 1.5 (Elastic) | 5607.06 | 13.94 | 0.25% | 77.00% | ₹463,839.38 | ₹728.05 | ₹107,976.65 | +656.92 |
| 2.0 | 2.0 (Highly Elastic) | 5616.44 | 4.56 | 0.08% | 92.48% | ₹464,564.57 | ₹239.80 | ₹108,701.84 | +1,382.11 |

---

### 4.1 Microeconomic Trace of Elasticity Scenarios (Why |Ed| = 0.5 and 1.0 Match Fixed Pricing)

The elasticity sensitivity experiment evaluates four distinct consumer responsiveness scenarios: $|E_d| \in \{0.5, 1.0, 1.5, 2.0\}$. The summary shows that:
- $|E_d| = 0.5$ (Inelastic): **60.60 unsold units**, waste rate 1.08%, profit diff ₹0.00 (identical to Fixed).
- $|E_d| = 1.0$ (Unitary Elastic): **60.60 unsold units**, waste rate 1.08%, profit diff ₹0.00 (identical to Fixed).
- $|E_d| = 1.5$ (Elastic): **13.94 unsold units**, waste rate 0.25%, profit diff +₹656.92.
- $|E_d| = 2.0$ (Highly Elastic): **4.56 unsold units**, waste rate 0.08%, profit diff +₹1,382.11.

**Microeconomic Explanation & Profitability Safeguard**:
1. **Inelastic Demand ($|E_d| = 0.5 < 1.0$)**:
   - In standard economics, marginal revenue when demand is inelastic is negative: $\frac{dR}{dQ} = P \left(1 - \frac{1}{|E_d|}\right) < 0$.
   - A 10% price markdown increases daily demand by only $0.5 \times 10\% = 5\%$. The quantity gain is insufficient to offset the price cut, so total revenue falls.
   - For all 6 surplus batches, applying markdowns under $|E_d| = 0.5$ causes net retail profit to drop significantly (e.g. Full Cream Milk profit drops by ₹65.09; Baguette profit drops by ₹10.04).
2. **Unitary Elastic Demand ($|E_d| = 1.0$)**:
   - Under the linear demand specification $Q(d) = Q_0(1 + d)$ and price $P(d) = P_0(1 - d)$, revenue per day is $R(d) = P_0 Q_0 (1 - d^2) < P_0 Q_0$ for any discount $d > 0$.
   - While additional volume is sold, the discount applies across all sold units in the batch, causing total revenue to decline relative to regular price for almost all batches.
3. **The Pricing Engine's Profitability Protection Rule**:
   - The engine explicitly tests candidate discounts against the fixed baseline: `if cand_profit > best_profit + 0.05`.
   - If discounting reduces net profit, the engine **refuses to discount** and reports: `"Retained regular price: markdown would reduce net profit (elasticity insufficient to offset price drop)"`.
   - Rather than destroying retailer profit to chase vanity clearance volume, the engine protects the retailer's bottom line.
   - When demand becomes elastic ($|E_d| = 1.5$ and $2.0$), the volume expansion ($+15\%$ to $+30\%$ for a $10\%$ cut) outweighs margin compression, unlocking substantial waste reductions (77.00% and 92.48%) and net profit improvements (+₹656.92 and +₹1,382.11).

---

## 5. Metric Definitions & Accounting Reconciliations

1. **Units Sold**: Deterministic expected continuous sales over remaining shelf life.
2. **COGS (Cost of Goods Sold)**: `Units Sold * Unit Cost`.
3. **Gross Profit on Sold Units**: `Revenue - COGS`.
4. **Waste Loss (Spoilage Cost)**: `Unsold Units * Unit Cost`.
5. **Total Initial Inventory Cost**: `COGS + Waste Loss = Initial Stock * Unit Cost`.
6. **Net Retail Profit**: `Gross Profit - Waste Loss = Revenue - Total Initial Inventory Cost`.
7. **Waste Rate (%)**: `(Unsold Units / Initial Stock) * 100`.
8. **Waste Reduction (%)**: `((Fixed Waste - Dynamic Waste) / Fixed Waste) * 100` (safe handling for 0 baseline).

### 5.1 Mathematical Accounting Reconciliation Audit

All summary tables and sensitivity scenarios have been audited to ensure 100% mathematical reconciliation:
1. **Physical Inventory Balance**:
   - $\text{Units Sold} + \text{Unsold Units} = \text{Total Initial Stock} = 5,621.00$ units across every discount cap and elasticity scenario (variance: 0.0000).
2. **Cost Reconciliation**:
   - $\text{COGS} + \text{Waste Loss} = \text{Total Initial Inventory Cost} = ₹355,862.73$ across all scenarios (variance: 0.0000).
3. **Profit Reconciliation**:
   - $\text{Net Retail Profit} = \text{Gross Profit} - \text{Waste Loss} = \text{Revenue} - \text{Total Initial Inventory Cost}$ holds exactly for all rows (variance: 0.0000).
4. **Category vs. Aggregate Consistency**:
   - Category-level fixed totals sum exactly to the aggregate fixed baseline ($₹463,182.46$ revenue, $₹107,319.73$ net profit, $60.60$ unsold units).
   - Category-level dynamic totals sum exactly to the aggregate dynamic 35% discount scenario ($₹463,354.07$ revenue, $₹107,491.34$ net profit, $38.42$ unsold units).
   - Consistent formulas are applied uniformly across category breakdowns and aggregate sensitivity summaries.

---

## 6. Model Assumptions & Limitations for Judges

- **Synthetic Data**: Inventory, demand rates, and price points are algorithmically generated for hackathon benchmarking; they do not represent audited supermarket financial statements.
- **Continuous Expectation Sales**: Sales figures represent expected values under a deterministic continuous demand rate rather than discrete stochastic Poisson draws.
- **Independent Product Demand**: Cross-product substitution and category cannibalization effects are outside the current model scope.
- **Price Floor Constraint**: Hard boundary prevents selling prices from dropping below wholesale unit cost, ensuring retailers never incur cash losses on sold items.
- **Context-Specific Optimality**: No configuration is universally optimal; maximum clearance effectiveness depends directly on shelf-life length and customer price elasticity.
