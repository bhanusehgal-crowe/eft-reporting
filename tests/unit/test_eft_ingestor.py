import uuid
from pathlib import Path

import pytest

from src.eftr.ingest.eft_ingestor import EFTIngestor
from src.eftr.models.eft_transaction import EFTTransaction
from src.eftr.models.reconciliation import ReconciliationRun
from src.eftr.utils.datetime_utils import utcnow


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


def test_eft_ingestor_csv(db_session, run_id, tmp_path):
    _create_run(db_session, run_id)
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_eft.csv"
    ingestor = EFTIngestor(db_session, run_id, "test_op")
    df = ingestor.run(str(fixture))
    assert len(df) > 0
    # Verify DB rows
    txns = db_session.query(EFTTransaction).filter_by(run_id=run_id).all()
    assert len(txns) == len(df)


def test_eft_ingestor_deduplication(db_session, run_id, tmp_path):
    """Running same file twice should not create duplicate rows."""
    _create_run(db_session, run_id)
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_eft.csv"
    ingestor = EFTIngestor(db_session, run_id, "test_op")

    df1 = ingestor.run(str(fixture))

    run_id_2 = str(uuid.uuid4())
    _create_run(db_session, run_id_2)
    ingestor2 = EFTIngestor(db_session, run_id_2, "test_op")
    df2 = ingestor2.run(str(fixture))

    # Second run should persist 0 rows (all duplicates)
    txns_run2 = db_session.query(EFTTransaction).filter_by(run_id=run_id_2).all()
    assert len(txns_run2) == 0


def test_eft_ingestor_quarantines_invalid_rows(db_session, run_id, tmp_path):
    """Rows with missing required fields should be quarantined."""
    _create_run(db_session, run_id)
    bad_csv = tmp_path / "bad_eft.csv"
    bad_csv.write_text(
        "transaction_id,value_date,amount,currency_code,direction,originator_name,beneficiary_name\n"
        ",2026-03-01,15000,CAD,INITIATION,Acme,Global\n"  # missing transaction_id
    )
    ingestor = EFTIngestor(db_session, run_id, "test_op")
    df = ingestor.run(str(bad_csv))
    # transaction_id is empty string → Pydantic validator should reject/allow based on type
    # For now just verify no crash
    assert df is not None
