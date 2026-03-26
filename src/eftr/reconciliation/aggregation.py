"""24-hour aggregation engine — pandas-free."""
import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.rule import RuleFinding
from src.eftr.utils.snapshot import load_snapshot

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


class AggregationEngine:
    def __init__(self, session: Session, run_id: str, operator_id: str):
        self.session = session
        self.run_id = run_id
        self.operator_id = operator_id

    def _audit(self, event_type: str, severity: str, message: str, detail: dict | None = None):
        self.session.add(AuditLog(
            log_id=str(uuid.uuid4()), run_id=self.run_id, event_type=event_type,
            severity=severity, component="aggregation_engine", operator_id=self.operator_id,
            message=message, detail=detail or {}, created_at=datetime.utcnow(),
        ))

    def _party_id(self, row: dict) -> str:
        direction = str(row.get("direction", ""))
        if direction == "RECEIPT":
            return str(row.get("beneficiary_account") or row.get("beneficiary_name") or "UNKNOWN")
        return str(row.get("originator_account") or row.get("originator_name") or "UNKNOWN")

    def run(self) -> dict:
        eft_path = Path(settings.data_processed_dir) / "eft" / f"{self.run_id}_eft.csv"
        rep_path = Path(settings.data_processed_dir) / "reported" / f"{self.run_id}_reported.csv"
        eft_rows = load_snapshot(eft_path)
        rep_rows = load_snapshot(rep_path)

        if not eft_rows:
            return {"aggregation_groups": 0, "breaches": 0, "over_reporting": 0}

        reported_ids = {str(r.get("reported_transaction_id", "")) for r in rep_rows}

        # Group by (party_id, direction, value_date) — static 24-hour window
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for row in eft_rows:
            key = (self._party_id(row), str(row.get("direction", "")), str(row.get("value_date", ""))[:10])
            groups[key].append(row)

        breach_count = over_report_count = group_count = 0
        for (party_id, direction, value_date), group in groups.items():
            if len(group) < 2:
                continue
            group_count += 1
            try:
                total_cad = sum(Decimal(str(r.get("cad_amount") or 0)) for r in group)
            except Exception:
                total_cad = Decimal("0")
            tx_ids = [str(r.get("transaction_id", "")) for r in group]
            reported_in_group = [tid for tid in tx_ids if tid in reported_ids]

            if total_cad >= FINTRAC_THRESHOLD_CAD and not reported_in_group:
                self.session.add(RuleFinding(
                    finding_id=str(uuid.uuid4()), run_id=self.run_id, rule_id="",
                    rule_code="FINTRAC_24HR_AGGREGATION", rule_version=1,
                    transaction_id=",".join(tx_ids[:5]), severity="BREACH",
                    detail={
                        "party_id": party_id, "direction": direction, "value_date": value_date,
                        "total_cad_amount": str(total_cad), "transaction_count": len(tx_ids),
                        "transaction_ids": tx_ids, "reported_count": 0,
                        "reason": f"Aggregated EFTs of CAD {total_cad} within 24h not reported",
                    },
                ))
                breach_count += 1
            elif total_cad < FINTRAC_THRESHOLD_CAD and reported_in_group:
                self.session.add(RuleFinding(
                    finding_id=str(uuid.uuid4()), run_id=self.run_id, rule_id="",
                    rule_code="FINTRAC_OVER_REPORTING", rule_version=1,
                    transaction_id=",".join(reported_in_group[:5]), severity="INFO",
                    detail={
                        "party_id": party_id, "direction": direction, "value_date": value_date,
                        "total_cad_amount": str(total_cad),
                        "reason": "Aggregated EFTs below $10,000 threshold were reported",
                    },
                ))
                over_report_count += 1

        self.session.commit()
        return {"aggregation_groups": group_count, "breaches": breach_count,
                "over_reporting": over_report_count}
