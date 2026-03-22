import uuid
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from src.eftr.models.reconciliation import ReconciliationResult, ReconciliationRun
from src.eftr.models.rule import RuleFinding
from src.eftr.reconciliation.engine import ReconciliationEngine
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
    """Write parquet snapshots to tmp_path and patch settings."""
    eft_dir = tmp_path / "eft"
    rep_dir = tmp_path / "reported"
    eft_dir.mkdir(parents=True)
    rep_dir.mkdir(parents=True)
    save_parquet(eft_df, eft_dir / f"{run_id}_eft.parquet")
    if not rep_df.empty:
        save_parquet(rep_df, rep_dir / f"{run_id}_reported.parquet")

    import config.settings as s_mod
    monkeypatch.setattr(s_mod.settings, "data_processed_dir", str(tmp_path))


def test_exact_match(db_session, run_id, tmp_path, monkeypatch):
    _create_run(db_session, run_id)

    eft_df = pd.DataFrame([{
        "transaction_id": "EFT001",
        "value_date": "2026-03-01",
        "cad_amount": 15000.0,
        "beneficiary_account": "ACC-2001",
        "direction": "INITIATION",
        "originator_name": "Acme",
        "beneficiary_name": "Global",
    }])
    rep_df = pd.DataFrame([{
        "reported_id": str(uuid.uuid4()),
        "reported_transaction_id": "EFT001",
        "report_date": "2026-03-03",
        "reported_amount": 15000.0,
        "reported_cad_amount": 15000.0,
    }])

    _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch)
    engine = ReconciliationEngine(db_session, run_id, "test_op")
    result = engine.run()

    assert result["matched"] == 1
    assert result["missed"] == 0
    assert result["phantom"] == 0

    db_result = db_session.query(ReconciliationResult).filter_by(
        run_id=run_id, status="MATCHED"
    ).first()
    assert db_result is not None
    assert db_result.match_method == "EXACT_ID"


def test_missed_transaction_breach(db_session, run_id, tmp_path, monkeypatch):
    """EFT >= $10k with no reported match should produce MISSED + BREACH finding."""
    _create_run(db_session, run_id)

    eft_df = pd.DataFrame([{
        "transaction_id": "EFT010",
        "value_date": "2026-03-12",
        "cad_amount": 13000.0,
        "beneficiary_account": "ACC-2007",
        "direction": "INITIATION",
        "originator_name": "West Corp",
        "beneficiary_name": "Tokyo Corp",
    }])
    rep_df = pd.DataFrame()

    _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch)
    engine = ReconciliationEngine(db_session, run_id, "test_op")
    result = engine.run()

    assert result["missed"] == 1
    assert result["breaches"] == 1

    breach = db_session.query(RuleFinding).filter_by(
        run_id=run_id, rule_code="FINTRAC_SINGLE_THRESHOLD"
    ).first()
    assert breach is not None
    assert breach.severity == "BREACH"


def test_phantom_transaction(db_session, run_id, tmp_path, monkeypatch):
    """Reported with no matching EFT should be PHANTOM."""
    _create_run(db_session, run_id)

    eft_df = pd.DataFrame(columns=["transaction_id", "value_date", "cad_amount", "beneficiary_account", "direction", "originator_name", "beneficiary_name"])
    rep_df = pd.DataFrame([{
        "reported_id": str(uuid.uuid4()),
        "reported_transaction_id": "EFT999",
        "report_date": "2026-03-10",
        "reported_amount": 20000.0,
        "reported_cad_amount": 20000.0,
    }])

    # Need at least one empty eft parquet
    eft_dir = tmp_path / "eft"
    rep_dir = tmp_path / "reported"
    eft_dir.mkdir(parents=True)
    rep_dir.mkdir(parents=True)
    save_parquet(eft_df, eft_dir / f"{run_id}_eft.parquet")
    save_parquet(rep_df, rep_dir / f"{run_id}_reported.parquet")

    import config.settings as s_mod
    monkeypatch.setattr(s_mod.settings, "data_processed_dir", str(tmp_path))

    engine = ReconciliationEngine(db_session, run_id, "test_op")
    result = engine.run()

    assert result["phantom"] == 1


def test_below_threshold_no_breach(db_session, run_id, tmp_path, monkeypatch):
    """EFT < $10k with no report should be MISSED but NOT a BREACH."""
    _create_run(db_session, run_id)

    eft_df = pd.DataFrame([{
        "transaction_id": "EFT020",
        "value_date": "2026-03-20",
        "cad_amount": 9500.0,
        "beneficiary_account": "ACC-2011",
        "direction": "INITIATION",
        "originator_name": "Tech Startup",
        "beneficiary_name": "Silicon Corp",
    }])
    rep_df = pd.DataFrame()

    _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch)
    engine = ReconciliationEngine(db_session, run_id, "test_op")
    result = engine.run()

    assert result["missed"] == 1
    assert result["breaches"] == 0
