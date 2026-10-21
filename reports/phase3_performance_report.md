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

## 3. Feature 2: Maximum-Discount Sensitivity Analysis

| Discount Cap | Expected Units Sold | Unsold Units (Waste) | Waste Rate (%) | Waste Red. vs Fixed (%) | Total Revenue (INR) | Gross Profit (INR) | Waste Loss (INR) | Net Retail Profit (INR) | Profit Diff vs Fixed (INR) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Fixed (0%) | 5560.40 | 60.60 | 1.08% | 0.00% | ₹463,182.46 | ₹110,639.35 | ₹3,319.62 | ₹107,319.73 | +0.00 |
| 10% | 5579.40 | 41.60 | 0.74% | 31.35% | ₹463,332.53 | ₹109,765.74 | ₹2,295.94 | ₹107,469.80 | +150.07 |
| 20% | 5581.92 | 39.08 | 0.70% | 35.51% | ₹463,353.99 | ₹109,660.45 | ₹2,169.19 | ₹107,491.26 | +171.53 |
| 30% | 5582.58 | 38.42 | 0.68% | 36.60% | ₹463,354.07 | ₹109,627.33 | ₹2,135.99 | ₹107,491.34 | +171.61 |
| 35% | 5582.58 | 38.42 | 0.68% | 36.60% | ₹463,354.07 | ₹109,627.33 | ₹2,135.99 | ₹107,491.34 | +171.61 |

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

## 5. Metric Definitions & Accounting Reconciliations

1. **Units Sold**: Deterministic expected continuous sales over remaining shelf life.
2. **COGS (Cost of Goods Sold)**: `Units Sold * Unit Cost`.
3. **Gross Profit on Sold Units**: `Revenue - COGS`.
4. **Waste Loss (Spoilage Cost)**: `Unsold Units * Unit Cost`.
5. **Total Initial Inventory Cost**: `COGS + Waste Loss = Initial Stock * Unit Cost`.
6. **Net Retail Profit**: `Gross Profit - Waste Loss = Revenue - Total Initial Inventory Cost`.
7. **Waste Rate (%)**: `(Unsold Units / Initial Stock) * 100`.
8. **Waste Reduction (%)**: `((Fixed Waste - Dynamic Waste) / Fixed Waste) * 100` (safe handling for 0 baseline).

---

## 6. Model Assumptions & Limitations for Judges

- **Synthetic Data**: Inventory, demand rates, and price points are algorithmically generated for hackathon benchmarking; they do not represent audited supermarket financial statements.
- **Continuous Expectation Sales**: Sales figures represent expected values under a deterministic continuous demand rate rather than discrete stochastic Poisson draws.
- **Independent Product Demand**: Cross-product substitution and category cannibalization effects are outside the current model scope.
- **Price Floor Constraint**: Hard boundary prevents selling prices from dropping below wholesale unit cost, ensuring retailers never incur cash losses on sold items.
- **Context-Specific Optimality**: No configuration is universally optimal; maximum clearance effectiveness depends directly on shelf-life length and customer price elasticity.
