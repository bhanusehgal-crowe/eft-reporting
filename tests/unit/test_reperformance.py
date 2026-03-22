from decimal import Decimal

import pandas as pd
import pytest

from src.eftr.reperformance.calculators import aggregation_calc, threshold_calc


def test_threshold_calc_correctly_identifies_breach():
    eft_df = pd.DataFrame([
        {"transaction_id": "EFT001", "cad_amount": 15000.0},
        {"transaction_id": "EFT002", "cad_amount": 9500.0},
    ])
    rep_df = pd.DataFrame([
        {"reported_transaction_id": "EFT001"},
    ])
    results = threshold_calc.calculate(eft_df, rep_df)
    # EFT002 is below threshold and unreported → should_be_reported=False, was_reported=False → no variance
    # EFT001 is above threshold and reported → match → no variance
    assert len(results) == 0


def test_threshold_calc_missed_report():
    eft_df = pd.DataFrame([
        {"transaction_id": "EFT010", "cad_amount": 13000.0},
    ])
    rep_df = pd.DataFrame()
    results = threshold_calc.calculate(eft_df, rep_df)
    assert len(results) == 1
    assert results[0]["status"] == "BREACH"
    assert results[0]["transaction_id"] == "EFT010"


def test_threshold_calc_over_reported():
    eft_df = pd.DataFrame([
        {"transaction_id": "EFT009", "cad_amount": 8500.0},
    ])
    rep_df = pd.DataFrame([
        {"reported_transaction_id": "EFT009"},
    ])
    results = threshold_calc.calculate(eft_df, rep_df)
    # Below threshold but reported → should_be_reported=False, was_reported=True → VARIANCE
    assert len(results) == 1
    assert results[0]["status"] == "VARIANCE"


def test_aggregation_calc_breach():
    eft_df = pd.DataFrame([
        {
            "transaction_id": f"EFT01{i}",
            "value_date": "2026-03-13",
            "cad_amount": 3500.0,
            "direction": "RECEIPT",
            "beneficiary_account": "ACC-1007",
            "beneficiary_name": "Client A",
            "originator_account": "ACC-5001",
            "originator_name": "Euro Bank",
        }
        for i in range(1, 5)
    ])
    rep_df = pd.DataFrame()
    results = aggregation_calc.calculate(eft_df, rep_df)
    assert len(results) == 1
    assert results[0]["status"] == "BREACH"
    assert Decimal(results[0]["reperformed_value"]) == Decimal("14000")


def test_aggregation_calc_no_breach_when_reported():
    eft_df = pd.DataFrame([
        {
            "transaction_id": f"EFT02{i}",
            "value_date": "2026-03-14",
            "cad_amount": 3500.0,
            "direction": "RECEIPT",
            "beneficiary_account": "ACC-1008",
            "beneficiary_name": "Client B",
            "originator_account": "ACC-5002",
            "originator_name": "US Bank",
        }
        for i in range(1, 5)
    ])
    rep_df = pd.DataFrame([
        {"reported_transaction_id": f"EFT02{i}"}
        for i in range(1, 5)
    ])
    results = aggregation_calc.calculate(eft_df, rep_df)
    assert len(results) == 0
