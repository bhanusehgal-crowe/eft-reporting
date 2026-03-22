import uuid
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from src.eftr.models.reconciliation import ReconciliationRun
from src.eftr.models.rule import Rule, RuleFinding
from src.eftr.rules.engine import RulesEngine
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


def _seed_rule(session, rule_code, rule_type, severity, parameters=None):
    rule = Rule(
        rule_id=str(uuid.uuid4()),
        rule_code=rule_code,
        version=1,
        rule_name=rule_code,
        description=rule_code,
        rule_type=rule_type,
        parameters=parameters or {},
        severity=severity,
        effective_from=date(2020, 1, 1),
        effective_to=None,
        is_active=True,
        change_reason="test",
        changed_by="test",
        created_at=utcnow(),
    )
    session.add(rule)
    session.commit()
    return rule


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


def test_threshold_breach_finding(db_session, run_id, tmp_path, monkeypatch):
    """FINTRAC_SINGLE_THRESHOLD rule produces BREACH for unreported $15k EFT."""
    _create_run(db_session, run_id)
    _seed_rule(db_session, "FINTRAC_SINGLE_THRESHOLD", "THRESHOLD", "BREACH",
               {"threshold_cad": 10000})

    eft_df = pd.DataFrame([{
        "transaction_id": "EFT001",
        "value_date": "2026-03-01",
        "cad_amount": 15000.0,
        "currency_code": "CAD",
        "direction": "INITIATION",
        "originator_name": "Acme Corp",
        "beneficiary_name": "Global Ltd",
        "cad_conversion_rate": None,
    }])
    rep_df = pd.DataFrame()

    _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch)
    engine = RulesEngine(db_session, run_id, "test_op")
    result = engine.run()

    assert result["findings"] >= 1
    finding = db_session.query(RuleFinding).filter_by(
        run_id=run_id, rule_code="FINTRAC_SINGLE_THRESHOLD"
    ).first()
    assert finding is not None
    assert finding.severity == "BREACH"


def test_deadline_breach_finding(db_session, run_id, tmp_path, monkeypatch):
    """FINTRAC_FILING_DEADLINE: EFTR filed on day 8 → BREACH."""
    _create_run(db_session, run_id)
    _seed_rule(db_session, "FINTRAC_FILING_DEADLINE", "DEADLINE", "BREACH",
               {"max_business_days": 5})

    eft_df = pd.DataFrame([{
        "transaction_id": "EFT006",
        "value_date": "2026-03-08",
        "cad_amount": 25000.0,
        "currency_code": "CAD",
        "direction": "INITIATION",
        "originator_name": "Northern Corp",
        "beneficiary_name": "Caribbean Holdings",
        "cad_conversion_rate": None,
    }])
    # Filed on 2026-03-20: that's >5 business days after 2026-03-08
    rep_df = pd.DataFrame([{
        "reported_id": str(uuid.uuid4()),
        "reported_transaction_id": "EFT006",
        "report_date": "2026-03-20",
        "reported_amount": 25000.0,
        "reported_cad_amount": 25000.0,
        "report_reference": "RPT-006",
        "reporting_entity_id": "MAPLE-BANK",
        "report_type": "EFTR",
        "direction": "INITIATION",
    }])

    _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch)
    engine = RulesEngine(db_session, run_id, "test_op")
    result = engine.run()

    finding = db_session.query(RuleFinding).filter_by(
        run_id=run_id, rule_code="FINTRAC_FILING_DEADLINE"
    ).first()
    assert finding is not None
    assert finding.severity == "BREACH"


def test_over_reporting_finding(db_session, run_id, tmp_path, monkeypatch):
    """FINTRAC_OVER_REPORTING: EFT of $8500 was reported → INFO finding."""
    _create_run(db_session, run_id)
    _seed_rule(db_session, "FINTRAC_OVER_REPORTING", "THRESHOLD", "INFO",
               {"threshold_cad": 10000})

    eft_df = pd.DataFrame([{
        "transaction_id": "EFT009",
        "value_date": "2026-03-10",
        "cad_amount": 8500.0,
        "currency_code": "CAD",
        "direction": "INITIATION",
        "originator_name": "Local Shop Ltd",
        "beneficiary_name": "US Vendor LLC",
        "cad_conversion_rate": None,
    }])
    rep_df = pd.DataFrame([{
        "reported_id": str(uuid.uuid4()),
        "reported_transaction_id": "EFT009",
        "report_date": "2026-03-12",
        "reported_amount": 8500.0,
        "reported_cad_amount": 8500.0,
        "report_reference": "RPT-009",
        "reporting_entity_id": "MAPLE-BANK",
        "report_type": "EFTR",
        "direction": "INITIATION",
    }])

    _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch)
    engine = RulesEngine(db_session, run_id, "test_op")
    result = engine.run()

    finding = db_session.query(RuleFinding).filter_by(
        run_id=run_id, rule_code="FINTRAC_OVER_REPORTING"
    ).first()
    assert finding is not None
    assert finding.severity == "INFO"


def test_no_findings_for_clean_transaction(db_session, run_id, tmp_path, monkeypatch):
    """Clean $15k EFT with on-time EFTR → no BREACH findings."""
    _create_run(db_session, run_id)
    _seed_rule(db_session, "FINTRAC_SINGLE_THRESHOLD", "THRESHOLD", "BREACH",
               {"threshold_cad": 10000})
    _seed_rule(db_session, "FINTRAC_FILING_DEADLINE", "DEADLINE", "BREACH",
               {"max_business_days": 5})

    eft_df = pd.DataFrame([{
        "transaction_id": "EFT001",
        "value_date": "2026-03-01",
        "cad_amount": 15000.0,
        "currency_code": "CAD",
        "direction": "INITIATION",
        "originator_name": "Acme Corp",
        "beneficiary_name": "Global Ltd",
        "cad_conversion_rate": None,
    }])
    rep_df = pd.DataFrame([{
        "reported_id": str(uuid.uuid4()),
        "reported_transaction_id": "EFT001",
        "report_date": "2026-03-03",  # Day 2 — well within deadline
        "reported_amount": 15000.0,
        "reported_cad_amount": 15000.0,
        "report_reference": "RPT-001",
        "reporting_entity_id": "MAPLE-BANK",
        "report_type": "EFTR",
        "direction": "INITIATION",
    }])

    _write_snapshots(run_id, eft_df, rep_df, tmp_path, monkeypatch)
    engine = RulesEngine(db_session, run_id, "test_op")
    engine.run()

    breach_findings = db_session.query(RuleFinding).filter_by(
        run_id=run_id, severity="BREACH"
    ).all()
    assert len(breach_findings) == 0
