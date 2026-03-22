import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.reconciliation import ReconciliationResult
from src.eftr.models.rule import RuleFinding
from src.eftr.utils.hashing import sha256_file


class MissedTransactionsReporter:
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
            component="report_generator",
            operator_id=self.operator_id,
            message=message,
            detail=detail or {},
            created_at=datetime.utcnow(),
        )
        self.session.add(entry)

    def generate(self) -> str:
        exports_dir = Path(settings.data_exports_dir)
        exports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        output_path = exports_dir / f"missed_transactions_{self.run_id}_{timestamp}.xlsx"

        # Query reconciliation results for MISSED and PHANTOM
        missed_results = self.session.execute(
            select(ReconciliationResult).where(
                ReconciliationResult.run_id == self.run_id,
                ReconciliationResult.status.in_(["MISSED", "PHANTOM"]),
            )
        ).scalars().all()

        # Query rule findings for BREACH severity
        breach_findings = self.session.execute(
            select(RuleFinding).where(
                RuleFinding.run_id == self.run_id,
                RuleFinding.severity == "BREACH",
            )
        ).scalars().all()

        all_findings = self.session.execute(
            select(RuleFinding).where(RuleFinding.run_id == self.run_id)
        ).scalars().all()

        # Build summary
        summary_data = {
            "Metric": [
                "Run ID",
                "Report Generated (UTC)",
                "Missed Transactions",
                "Phantom Transactions",
                "Total BREACH Findings",
                "Total WARN Findings",
                "Total INFO Findings",
            ],
            "Value": [
                self.run_id,
                timestamp,
                sum(1 for r in missed_results if r.status == "MISSED"),
                sum(1 for r in missed_results if r.status == "PHANTOM"),
                sum(1 for f in all_findings if f.severity == "BREACH"),
                sum(1 for f in all_findings if f.severity == "WARN"),
                sum(1 for f in all_findings if f.severity == "INFO"),
            ],
        }
        summary_df = pd.DataFrame(summary_data)

        # Build missed detail sheet
        missed_rows = []
        for r in missed_results:
            missed_rows.append(
                {
                    "result_id": r.result_id,
                    "status": r.status,
                    "eft_transaction_id": r.eft_transaction_id or "",
                    "reported_id": r.reported_id or "",
                    "match_method": r.match_method or "",
                    "variance_amount": float(r.variance_amount) if r.variance_amount else "",
                    "detail": str(r.detail),
                }
            )
        missed_df = pd.DataFrame(missed_rows) if missed_rows else pd.DataFrame(
            columns=["result_id", "status", "eft_transaction_id", "reported_id", "match_method", "variance_amount", "detail"]
        )

        # Build rule breaches sheet
        breach_rows = []
        for f in all_findings:
            breach_rows.append(
                {
                    "finding_id": f.finding_id,
                    "severity": f.severity,
                    "rule_code": f.rule_code,
                    "rule_version": f.rule_version,
                    "transaction_id": f.transaction_id or "",
                    "detail": str(f.detail),
                    "created_at": str(f.created_at),
                }
            )
        breach_df = pd.DataFrame(breach_rows) if breach_rows else pd.DataFrame(
            columns=["finding_id", "severity", "rule_code", "rule_version", "transaction_id", "detail", "created_at"]
        )

        # Write Excel workbook
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, sheet_name="Summary", index=False)
            missed_df.to_excel(writer, sheet_name="Missed Detail", index=False)
            breach_df.to_excel(writer, sheet_name="Rule Breaches", index=False)

        file_hash = sha256_file(output_path)
        self._audit(
            "REPORT_GENERATED",
            "INFO",
            f"Missed transactions report generated: {output_path.name}",
            {"output_path": str(output_path), "file_sha256": file_hash},
        )
        self.session.commit()
        return str(output_path)
