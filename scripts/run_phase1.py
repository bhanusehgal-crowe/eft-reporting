"""Phase 1 CLI: ingest → reconcile → rules → report."""
import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import Base, SessionLocal, engine
from config.logging import configure_logging, get_logger

configure_logging()
log = get_logger("phase1")

from src.eftr.ingest.eft_ingestor import EFTIngestor
from src.eftr.ingest.reported_ingestor import ReportedIngestor
from src.eftr.models.reconciliation import ReconciliationRun
from src.eftr.reconciliation.aggregation import AggregationEngine
from src.eftr.reconciliation.engine import ReconciliationEngine
from src.eftr.reconciliation.report import MissedTransactionsReporter
from src.eftr.rules.engine import RulesEngine
from src.eftr.utils.datetime_utils import utcnow

# Ensure tables exist
Base.metadata.create_all(engine)


def run_phase1(eft_file: str, reported_file: str, operator: str) -> dict:
    run_id = str(uuid.uuid4())
    log.info("phase1_started", run_id=run_id, operator=operator)

    with SessionLocal() as session:
        # Create run record
        run = ReconciliationRun(
            run_id=run_id,
            status="RUNNING",
            triggered_by="cli",
            operator_id=operator,
            started_at=utcnow(),
            parameters={"eft_file": eft_file, "reported_file": reported_file},
            created_at=utcnow(),
        )
        session.add(run)
        session.commit()

        try:
            # Step 1: Ingest EFTs
            log.info("ingesting_eft", run_id=run_id, file=eft_file)
            eft_ingestor = EFTIngestor(session, run_id, operator)
            eft_df = eft_ingestor.run(eft_file)
            log.info("eft_ingested", run_id=run_id, rows=len(eft_df))

            # Step 2: Ingest reported transactions
            log.info("ingesting_reported", run_id=run_id, file=reported_file)
            rep_ingestor = ReportedIngestor(session, run_id, operator)
            rep_df = rep_ingestor.run(reported_file)
            log.info("reported_ingested", run_id=run_id, rows=len(rep_df))

            # Step 3: Reconciliation
            log.info("running_reconciliation", run_id=run_id)
            recon_engine = ReconciliationEngine(session, run_id, operator)
            recon_summary = recon_engine.run()
            log.info("reconciliation_complete", run_id=run_id, **recon_summary)

            # Step 4: 24-hour aggregation check
            log.info("running_aggregation", run_id=run_id)
            agg_engine = AggregationEngine(session, run_id, operator)
            agg_summary = agg_engine.run()
            log.info("aggregation_complete", run_id=run_id, **agg_summary)

            # Step 5: Rules engine
            log.info("running_rules", run_id=run_id)
            rules_engine = RulesEngine(session, run_id, operator)
            rules_summary = rules_engine.run()
            log.info("rules_complete", run_id=run_id, **rules_summary)

            # Step 6: Generate missed transactions report
            log.info("generating_report", run_id=run_id)
            reporter = MissedTransactionsReporter(session, run_id, operator)
            report_path = reporter.generate()
            log.info("report_generated", run_id=run_id, path=report_path)

            # Mark run complete
            run.status = "COMPLETED"
            run.completed_at = utcnow()
            session.commit()

            summary = {
                "run_id": run_id,
                "status": "COMPLETED",
                "eft_rows": len(eft_df),
                "reported_rows": len(rep_df),
                "reconciliation": recon_summary,
                "aggregation": agg_summary,
                "rules": rules_summary,
                "report_path": report_path,
            }

            print("\n" + "=" * 60)
            print(f"Phase 1 Complete — Run ID: {run_id}")
            print("=" * 60)
            print(f"  EFT rows ingested:      {len(eft_df)}")
            print(f"  Reported rows ingested: {len(rep_df)}")
            print(f"  Matched:                {recon_summary.get('matched', 0)}")
            print(f"  Missed:                 {recon_summary.get('missed', 0)}")
            print(f"  Phantom:                {recon_summary.get('phantom', 0)}")
            print(f"  Threshold breaches:     {recon_summary.get('breaches', 0)}")
            print(f"  Aggregation breaches:   {agg_summary.get('breaches', 0)}")
            print(f"  Rule findings:          {rules_summary.get('findings', 0)}")
            print(f"  Report:                 {report_path}")
            print("=" * 60)

            return summary

        except Exception as exc:
            run.status = "FAILED"
            run.completed_at = utcnow()
            session.commit()
            log.error("phase1_failed", run_id=run_id, error=str(exc))
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Phase 1 pipeline")
    parser.add_argument("--eft", required=True, help="Path to EFT CSV/Excel file")
    parser.add_argument("--reported", required=True, help="Path to reported transactions CSV/Excel file")
    parser.add_argument("--operator", default="system", help="Operator ID")
    args = parser.parse_args()

    run_phase1(args.eft, args.reported, args.operator)
