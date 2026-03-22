import uuid
from decimal import Decimal

import pandas as pd
import pytest

from src.eftr.models.reconciliation import ReconciliationRun
from src.eftr.models.rule import RuleFinding
from src.eftr.reconciliation.aggregation import AggregationEngine
from src.eftr.utils.datetime_utils import utcnow
from src.eftr.utils.snapshot import save_parquet


def _create_run(session, run_id):
    run = ReconciliationRun(
        run_id=run_id,
        status="RUNNING",
        triggered_by="test",
        operator_id="test_op",
        started_at=utcnow(),
        parameters={},
        created_at=utcnow(),
    )
    session.add(run)
    session.commit()


def _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch):
    eft_dir = tmp_path / "eft"
    rep_dir = tmp_path / "reported"
    eft_dir.mkdir(parents=True, exist_ok=True)
    rep_dir.mkdir(parents=True, exist_ok=True)
    save_parquet(eft_df, eft_dir / f"{run_id}_eft.parquet")
    if rep_df is not None and not rep_df.empty:
        save_parquet(rep_df, rep_dir / f"{run_id}_reported.parquet")

    import config.settings as s_mod
    monkeypatch.setattr(s_mod.settings, "data_processed_dir", str(tmp_path))


def test_24hr_aggregation_breach(db_session, run_id, tmp_path, monkeypatch):
    """4 EFTs to same beneficiary totalling $14k on same day, none reported → BREACH."""
    _create_run(db_session, run_id)

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
        for i in range(1, 5)  # 4 × $3500 = $14000
    ])

    _write_snapshots(run_id, eft_df, None, tmp_path, monkeypatch)
    engine = AggregationEngine(db_session, run_id, "test_op")
    result = engine.run()

    assert result["breaches"] == 1
    finding = db_session.query(RuleFinding).filter_by(
        run_id=run_id, rule_code="FINTRAC_24HR_AGGREGATION"
    ).first()
    assert finding is not None
    assert finding.severity == "BREACH"
    assert "14000" in str(finding.detail.get("total_cad_amount", ""))


def test_24hr_aggregation_no_breach_below_threshold(db_session, run_id, tmp_path, monkeypatch):
    """3 EFTs totalling $9k → no breach."""
    _create_run(db_session, run_id)

    eft_df = pd.DataFrame([
        {
            "transaction_id": f"EFT02{i}",
            "value_date": "2026-03-14",
            "cad_amount": 3000.0,
            "direction": "RECEIPT",
            "beneficiary_account": "ACC-1008",
            "beneficiary_name": "Client B",
            "originator_account": "ACC-5002",
            "originator_name": "US Bank",
        }
        for i in range(1, 4)  # 3 × $3000 = $9000
    ])

    _write_snapshots(run_id, eft_df, None, tmp_path, monkeypatch)
    engine = AggregationEngine(db_session, run_id, "test_op")
    result = engine.run()

    assert result["breaches"] == 0


def test_24hr_aggregation_single_tx_not_grouped(db_session, run_id, tmp_path, monkeypatch):
    """Single transaction above threshold — not an aggregation breach (handled by threshold rule)."""
    _create_run(db_session, run_id)

    eft_df = pd.DataFrame([{
        "transaction_id": "EFT030",
        "value_date": "2026-03-15",
        "cad_amount": 15000.0,
        "direction": "INITIATION",
        "beneficiary_account": "ACC-9001",
        "beneficiary_name": "Big Corp",
        "originator_account": "ACC-1001",
        "originator_name": "Local Bank",
    }])

    _write_snapshots(run_id, eft_df, None, tmp_path, monkeypatch)
    engine = AggregationEngine(db_session, run_id, "test_op")
    result = engine.run()

    # Single tx is not grouped (len < 2)
    assert result["aggregation_groups"] == 0
    assert result["breaches"] == 0


def test_over_reporting_detected(db_session, run_id, tmp_path, monkeypatch):
    """Group below $10k but some reported → over-reporting INFO."""
    _create_run(db_session, run_id)

    eft_df = pd.DataFrame([
        {
            "transaction_id": f"EFT04{i}",
            "value_date": "2026-03-16",
            "cad_amount": 1500.0,
            "direction": "INITIATION",
            "originator_account": "ACC-1009",
            "originator_name": "Small Shop",
            "beneficiary_account": "ACC-9002",
            "beneficiary_name": "Vendor",
        }
        for i in range(1, 4)  # 3 × $1500 = $4500
    ])

    rep_df = pd.DataFrame([{
        "reported_id": str(uuid.uuid4()),
        "reported_transaction_id": "EFT041",
        "report_date": "2026-03-17",
        "reported_amount": 1500.0,
        "reported_cad_amount": 1500.0,
        "report_reference": "RPT-X01",
        "reporting_entity_id": "BANK",
        "report_type": "EFTR",
        "direction": "INITIATION",
    }])

    _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch)
    engine = AggregationEngine(db_session, run_id, "test_op")
    result = engine.run()

    assert result["over_reporting"] == 1
    finding = db_session.query(RuleFinding).filter_by(
        run_id=run_id, rule_code="FINTRAC_OVER_REPORTING"
    ).first()
    assert finding is not None
    assert finding.severity == "INFO"
