import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.reperformance import ReperformanceResult
from src.eftr.reperformance.calculators import aggregation_calc, fx_calc, threshold_calc
from src.eftr.utils.snapshot import load_parquet


class ReperformanceEngine:
    def __init__(self, session: Session, run_id: str, operator_id: str):
        self.session = session
        self.run_id = run_id
        self.operator_id = operator_id

    def _audit(self, event_type: str, severity: str, message: str, detail: dict | None = None):
        entry = AuditLog(
            log_id=str(uuid.uuid4()),
            run_id=self.run_id,
            event_type=event_type,
            severity=severity,
            component="reperformance_engine",
            operator_id=self.operator_id,
            message=message,
            detail=detail or {},
            created_at=datetime.utcnow(),
        )
        self.session.add(entry)

    def _load_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        eft_path = Path(settings.data_processed_dir) / "eft" / f"{self.run_id}_eft.parquet"
        rep_path = Path(settings.data_processed_dir) / "reported" / f"{self.run_id}_reported.parquet"
        eft_df = load_parquet(eft_path) if eft_path.exists() else pd.DataFrame()
        rep_df = load_parquet(rep_path) if rep_path.exists() else pd.DataFrame()
        return eft_df, rep_df

    def _persist_results(self, results: list[dict]):
        for r in results:
            result = ReperformanceResult(
                result_id=str(uuid.uuid4()),
                run_id=self.run_id,
                calculation_type=r["calculation_type"],
                period=r.get("period"),
                reported_value=r.get("reported_value"),
                reperformed_value=r.get("reperformed_value"),
                variance_absolute=r.get("variance_absolute"),
                variance_pct=r.get("variance_pct"),
                status=r["status"],
                threshold_rule_id=r.get("threshold_rule_id"),
                detail=r.get("detail", {}),
            )
            self.session.add(result)

    def run(self) -> dict:
        self._audit("REPERFORMANCE_STARTED", "INFO", "Starting reperformance")
        eft_df, rep_df = self._load_data()

        if eft_df.empty:
            self._audit("REPERFORMANCE_SKIPPED", "WARN", "No EFT data for reperformance")
            self.session.commit()
            return {"threshold": 0, "aggregation": 0, "fx": 0}

        threshold_results = threshold_calc.calculate(eft_df, rep_df)
        self._persist_results(threshold_results)

        agg_results = aggregation_calc.calculate(eft_df, rep_df)
        self._persist_results(agg_results)

        fx_results = fx_calc.calculate(eft_df)
        self._persist_results(fx_results)

        summary = {
            "threshold": len(threshold_results),
            "aggregation": len(agg_results),
            "fx": len(fx_results),
        }
        self._audit(
            "REPERFORMANCE_COMPLETE",
            "INFO",
            f"Reperformance complete: {summary}",
            summary,
        )
        self.session.commit()
        return summary
