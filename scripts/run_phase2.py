"""Phase 2 CLI: quality checks + reperformance."""
import argparse
import sys
import uuid
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import Base, SessionLocal, engine
from config.logging import configure_logging, get_logger

configure_logging()
log = get_logger("phase2")

from src.eftr.quality.checks import run_quality_checks
from src.eftr.reperformance.engine import ReperformanceEngine

Base.metadata.create_all(engine)


def run_phase2(run_id: str, operator: str) -> dict:
    log.info("phase2_started", run_id=run_id, operator=operator)

    from config.settings import settings
    from src.eftr.utils.snapshot import load_parquet

    eft_path = Path(settings.data_processed_dir) / "eft" / f"{run_id}_eft.parquet"
    rep_path = Path(settings.data_processed_dir) / "reported" / f"{run_id}_reported.parquet"

    eft_df = load_parquet(eft_path) if eft_path.exists() else pd.DataFrame()
    rep_df = load_parquet(rep_path) if rep_path.exists() else pd.DataFrame()

    with SessionLocal() as session:
        log.info("running_quality_checks", run_id=run_id)
        quality_ok = run_quality_checks(eft_df, rep_df, session, run_id, operator)
        if not quality_ok:
            log.error("quality_checks_failed", run_id=run_id)
            print("Pipeline halted: quality checks failed. Check audit_log for details.")
            return {"status": "HALTED"}

        log.info("running_reperformance", run_id=run_id)
        reperform_engine = ReperformanceEngine(session, run_id, operator)
        reperform_summary = reperform_engine.run()
        log.info("reperformance_complete", run_id=run_id, **reperform_summary)

    print("\n" + "=" * 60)
    print(f"Phase 2 Complete — Run ID: {run_id}")
    print("=" * 60)
    print(f"  Quality checks:         PASS")
    print(f"  Threshold variances:    {reperform_summary.get('threshold', 0)}")
    print(f"  Aggregation variances:  {reperform_summary.get('aggregation', 0)}")
    print(f"  FX variances:           {reperform_summary.get('fx', 0)}")
    print("=" * 60)

    return {"status": "COMPLETED", "reperformance": reperform_summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Phase 2 quality + reperformance")
    parser.add_argument("--run-id", required=True, help="Run ID from Phase 1")
    parser.add_argument("--operator", default="system", help="Operator ID")
    args = parser.parse_args()

    run_phase2(args.run_id, args.operator)
