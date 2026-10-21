"""Unit tests for synthetic grocery dataset generator in FreshPrice AI."""

from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.data_generator import (
    PRODUCT_CATALOG,
    REQUIRED_COLUMNS,
    generate_grocery_data,
    save_dataset,
)


def test_required_columns_and_unit_present():
    """Verify that all required columns, including 'unit', are present."""
    df = generate_grocery_data(num_records=120, seed=42)
    assert list(df.columns) == REQUIRED_COLUMNS
    assert "unit" in df.columns
    # Ensure no unit value is null or empty string
    assert df["unit"].notna().all()
    assert (df["unit"].str.strip().str.len() > 0).all()


def test_minimum_record_count():
    """Verify dataset meets the at-least-120-records requirement."""
    df_default = generate_grocery_data()
    assert len(df_default) >= 120

    # Test exact count generation
    df_150 = generate_grocery_data(num_records=150)
    assert len(df_150) == 150


def test_category_coverage():
    """Verify all 5 required realistic grocery categories are represented."""
    expected_categories = {"dairy", "bakery", "fruits", "vegetables", "packaged food"}
    df = generate_grocery_data(num_records=120, seed=42)
    generated_categories = set(df["category"].unique())
    assert expected_categories == generated_categories


def test_explicit_units_sample_check():
    """Verify specific required units are present in the generated dataset."""
    df = generate_grocery_data(num_records=120, seed=42)

    # Check key specific product units requested
    milk_units = df[df["product_name"].str.contains("Milk", case=False)]["unit"].unique()
    assert "per litre" in milk_units

    curd_units = df[df["product_name"].str.contains("Curd|Yogurt", case=False)]["unit"].unique()
    assert "per 500 g pack" in curd_units

    apple_units = df[df["product_name"].str.contains("Apple", case=False)]["unit"].unique()
    assert "per kilogram" in apple_units

    cauli_units = df[df["product_name"].str.contains("Cauliflower", case=False)]["unit"].unique()
    assert "per head" in cauli_units

    bread_units = df[df["product_name"].str.contains("Bread", case=False)]["unit"].unique()
    assert "per loaf" in bread_units

    potato_units = df[df["product_name"].str.contains("Potatoes", case=False)]["unit"].unique()
    assert "per kilogram" in potato_units

    pasta_units = df[df["product_name"].str.contains("Spaghetti", case=False)]["unit"].unique()
    assert "per 500 g pack" in pasta_units


def test_inr_prices_and_regular_price_greater_than_cost():
    """Verify valid INR prices and that regular_price is strictly greater than unit_cost."""
    df = generate_grocery_data(num_records=150, seed=42)

    # 1. unit_cost and regular_price must be positive floats
    assert (df["unit_cost"] > 0.0).all()
    assert (df["regular_price"] > 0.0).all()

    # 2. regular_price must strictly exceed unit_cost for every record
    assert (df["regular_price"] > df["unit_cost"]).all()

    # 3. Test realistic Indian grocery price scales (not small single digit USD/EUR amounts)
    # Fresh Milk should be priced between ₹50 and ₹85 per litre in INR
    milk_records = df[
        (df["product_name"].str.contains("Fresh Milk", case=False))
        & (df["unit"] == "per litre")
    ]
    assert len(milk_records) > 0
    assert (milk_records["regular_price"] >= 50.0).all()
    assert (milk_records["regular_price"] <= 85.0).all()

    # Buttermilk (Chaas) should be priced between ₹14 and ₹25 per pouch in INR
    buttermilk_records = df[df["product_name"].str.contains("Buttermilk", case=False)]
    assert len(buttermilk_records) > 0
    assert (buttermilk_records["regular_price"] >= 14.0).all()
    assert (buttermilk_records["regular_price"] <= 25.0).all()

    # Apples should be priced between ₹100 and ₹250 per kg in INR
    apple_records = df[df["product_name"].str.contains("Apple", case=False)]
    assert (apple_records["regular_price"] >= 100.0).all()
    assert (apple_records["regular_price"] <= 250.0).all()

    # Potatoes should be priced between ₹20 and ₹45 per kg in INR
    potato_records = df[df["product_name"].str.contains("Potatoes", case=False)]
    assert (potato_records["regular_price"] >= 20.0).all()
    assert (potato_records["regular_price"] <= 45.0).all()


def test_valid_numerical_values():
    """Verify valid values for stock, expiry, demand, and elasticity."""
    df = generate_grocery_data(num_records=120, seed=42)

    # initial_stock must be positive integer
    assert (df["initial_stock"] > 0).all()
    assert np.issubdtype(df["initial_stock"].dtype, np.integer)

    # days_to_expiry must be positive integer >= 1
    assert (df["days_to_expiry"] >= 1).all()
    assert np.issubdtype(df["days_to_expiry"].dtype, np.integer)

    # daily_demand must be positive
    assert (df["daily_demand"] > 0.0).all()

    # price_elasticity must be negative
    assert (df["price_elasticity"] < 0.0).all()
    assert (df["price_elasticity"] >= -5.0).all()


def test_reproducibility():
    """Verify that identical random seeds produce identical datasets."""
    df1 = generate_grocery_data(num_records=120, seed=123)
    df2 = generate_grocery_data(num_records=120, seed=123)
    pd.testing.assert_frame_equal(df1, df2)

    # Different seeds should produce different records
    df3 = generate_grocery_data(num_records=120, seed=999)
    assert not df1.equals(df3)


def test_save_dataset(tmp_path: Path):
    """Verify dataset can be saved to CSV and loaded back intact."""
    test_csv_path = tmp_path / "test_inventory.csv"
    df = generate_grocery_data(num_records=120, seed=42)
    saved_file = save_dataset(df, test_csv_path)

    assert saved_file.exists()
    loaded_df = pd.read_csv(saved_file)
    assert len(loaded_df) == 120
    assert list(loaded_df.columns) == REQUIRED_COLUMNS
    assert (loaded_df["regular_price"] > loaded_df["unit_cost"]).all()


def test_cli_execution(tmp_path: Path):
    """Verify CLI interface runs and generates output file."""
    output_path = tmp_path / "cli_generated.csv"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.data_generator",
            "--records",
            "120",
            "--seed",
            "77",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0
    assert output_path.exists()
    loaded_df = pd.read_csv(output_path)
    assert len(loaded_df) == 120
    assert "unit" in loaded_df.columns
