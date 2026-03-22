"""Full pipeline integration test using fixture CSVs."""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.database import Base, get_engine
from sqlalchemy.orm import sessionmaker

from src.eftr.ingest.eft_ingestor import EFTIngestor
from src.eftr.ingest.reported_ingestor import ReportedIngestor
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.reconciliation import ReconciliationResult, ReconciliationRun
from src.eftr.models.rule import RuleFinding
from src.eftr.reconciliation.aggregation import AggregationEngine
from src.eftr.reconciliation.engine import ReconciliationEngine
from src.eftr.rules.engine import RulesEngine
from src.eftr.utils.datetime_utils import utcnow


@pytest.fixture
def pipeline_session(tmp_path, monkeypatch):
    """In-memory DB session with patched settings for isolated temp dir."""
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    import config.settings as s_mod
    monkeypatch.setattr(s_mod.settings, "data_processed_dir", str(tmp_path / "processed"))
    monkeypatch.setattr(s_mod.settings, "data_exports_dir", str(tmp_path / "exports"))
    monkeypatch.setattr(s_mod.settings, "data_quarantine_dir", str(tmp_path / "quarantine"))

    yield session
    session.close()


def test_full_pipeline_with_fixtures(pipeline_session, tmp_path, monkeypatch):
    run_id = str(uuid.uuid4())
    operator = "integration_test"

    # Create run
    run = ReconciliationRun(
        run_id=run_id,
        status="RUNNING",
        triggered_by="test",
        operator_id=operator,
        started_at=utcnow(),
        parameters={},
        created_at=utcnow(),
    )
    pipeline_session.add(run)
    pipeline_session.commit()

    fixture_dir = Path(__file__).parent.parent / "fixtures"
    eft_file = fixture_dir / "sample_eft.csv"
    reported_file = fixture_dir / "sample_reported.csv"

    # Patch settings for this session
    import config.settings as s_mod
    monkeypatch.setattr(s_mod.settings, "data_processed_dir", str(tmp_path / "processed"))
    monkeypatch.setattr(s_mod.settings, "data_exports_dir", str(tmp_path / "exports"))
    monkeypatch.setattr(s_mod.settings, "data_quarantine_dir", str(tmp_path / "quarantine"))

    # Ingest
    eft_ingestor = EFTIngestor(pipeline_session, run_id, operator)
    eft_df = eft_ingestor.run(str(eft_file))
    assert len(eft_df) == 20

    rep_ingestor = ReportedIngestor(pipeline_session, run_id, operator)
    rep_df = rep_ingestor.run(str(reported_file))
    assert len(rep_df) == 13

    # Reconciliation
    recon_engine = ReconciliationEngine(pipeline_session, run_id, operator)
    recon_result = recon_engine.run()
    assert recon_result["matched"] > 0
    assert recon_result["missed"] > 0

    # Aggregation
    agg_engine = AggregationEngine(pipeline_session, run_id, operator)
    agg_result = agg_engine.run()

    # Audit log should have entries
    audit_entries = pipeline_session.query(AuditLog).filter_by(run_id=run_id).all()
    assert len(audit_entries) > 0

    # Reconciliation results persisted
    recon_rows = pipeline_session.query(ReconciliationResult).filter_by(run_id=run_id).all()
    assert len(recon_rows) == recon_result["matched"] + recon_result["missed"] + recon_result["phantom"]


def test_audit_log_append_only(pipeline_session, tmp_path, monkeypatch):
    """Audit log entries are never deleted; counts only grow."""
    run_id = str(uuid.uuid4())

    import config.settings as s_mod
    monkeypatch.setattr(s_mod.settings, "data_processed_dir", str(tmp_path / "processed"))

    run = ReconciliationRun(
        run_id=run_id,
        status="RUNNING",
        triggered_by="test",
        operator_id="test",
        started_at=utcnow(),
        parameters={},
        created_at=utcnow(),
    )
    pipeline_session.add(run)
    pipeline_session.commit()

    fixture_dir = Path(__file__).parent.parent / "fixtures"
    ingestor = EFTIngestor(pipeline_session, run_id, "test")
    ingestor.run(str(fixture_dir / "sample_eft.csv"))

    count_after_ingest = pipeline_session.query(AuditLog).filter_by(run_id=run_id).count()
    assert count_after_ingest > 0

    # Delete is not called; count only grows
    ingestor2 = ReportedIngestor(pipeline_session, run_id, "test")
    ingestor2.run(str(fixture_dir / "sample_reported.csv"))

    count_after_second = pipeline_session.query(AuditLog).filter_by(run_id=run_id).count()
    assert count_after_second >= count_after_ingest
