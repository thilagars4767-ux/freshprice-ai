# FreshPrice - Development Log

## Milestone 1.1: Indian Grocery Adaptation & INR Pricing
- **Date**: 2026-10-21
- **Status**: Completed & Verified.
- **Key Enhancements**:
  - **Currency Alignment**: All monetary figures (`unit_cost`, `regular_price`) transitioned to INR (Indian Rupees - ₹).
  - **Explicit Selling Units**: Added `unit` column identifying quantity per price quote (`per litre`, `per 500 g pack`, `per kilogram`, `per head`, `per loaf`, `per dozen`, etc.).
  - **Product-Specific Pricing**: Replaced generic category bounds with individual product-level wholesale cost ranges, retail markups, shelf lives, and price elasticity for 50 distinct Indian grocery items.
  - **Synthetic Data Disclaimer**: Explicitly documented assumptions and synthetic status of all prices.
  - **Dataset Regeneration**: Re-generated `data/synthetic_grocery_inventory.csv` (120 records, seed 42) adhering to all 10 columns.
  - **Test Suite Updates**:
    - `test_required_columns_and_unit_present`: Validates presence of `unit` and all other 9 required columns.
    - `test_explicit_units_sample_check`: Verifies explicit units for milk, curd/yogurt, apples, cauliflower, bread, potatoes, and pasta.
    - `test_inr_prices_and_regular_price_greater_than_cost`: Verifies positive values, realistic INR price scales, and strict `regular_price > unit_cost`.
    - `test_reproducibility`, `test_category_coverage`, `test_minimum_record_count`, `test_save_dataset`, and `test_cli_execution`.
- **Verification**:
  - 9/9 tests passed cleanly via `py -m pytest tests -v`.
