import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.rule import RuleFinding
from src.eftr.utils.snapshot import load_parquet

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


class AggregationEngine:
    """
    Groups EFT transactions by (party_id, direction) within static 24-hour windows
    and checks FINTRAC 24-hour aggregation rule compliance.
    """

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
            component="aggregation_engine",
            operator_id=self.operator_id,
            message=message,
            detail=detail or {},
            created_at=datetime.utcnow(),
        )
        self.session.add(entry)

    def _load_eft(self) -> pd.DataFrame:
        path = Path(settings.data_processed_dir) / "eft" / f"{self.run_id}_eft.parquet"
        return load_parquet(path) if path.exists() else pd.DataFrame()

    def _load_reported(self) -> pd.DataFrame:
        path = Path(settings.data_processed_dir) / "reported" / f"{self.run_id}_reported.parquet"
        return load_parquet(path) if path.exists() else pd.DataFrame()

    def _get_party_id(self, row: pd.Series) -> str:
        """Use beneficiary_account for RECEIPT, originator_account for INITIATION."""
        direction = str(row.get("direction", ""))
        if direction == "RECEIPT":
            return str(row.get("beneficiary_account") or row.get("beneficiary_name", "UNKNOWN"))
        return str(row.get("originator_account") or row.get("originator_name", "UNKNOWN"))

    def run(self) -> dict:
        eft_df = self._load_eft()
        rep_df = self._load_reported()

        if eft_df.empty:
            return {"aggregation_groups": 0, "breaches": 0, "over_reporting": 0}

        eft_df["value_date"] = pd.to_datetime(eft_df["value_date"]).dt.date
        eft_df["cad_amount"] = pd.to_numeric(eft_df["cad_amount"], errors="coerce").fillna(0)
        eft_df["party_id"] = eft_df.apply(self._get_party_id, axis=1)

        # Build reported set indexed by reported_transaction_id
        reported_ids = set()
        if not rep_df.empty:
            reported_ids = set(rep_df["reported_transaction_id"].astype(str))

        breach_count = 0
        over_report_count = 0
        group_count = 0

        # Group by (party_id, direction, value_date) — static 24-hour window = same date
        groups = eft_df.groupby(["party_id", "direction", "value_date"])
        for (party_id, direction, value_date), group in groups:
            if len(group) < 2:
                # Single transactions below threshold handled by single threshold rule
                continue

            group_count += 1
            total_cad = Decimal(str(group["cad_amount"].sum()))
            tx_ids = group["transaction_id"].astype(str).tolist()

            # Count how many of these are reported
            reported_in_group = [tid for tid in tx_ids if tid in reported_ids]

            if total_cad >= FINTRAC_THRESHOLD_CAD:
                if not reported_in_group:
                    # BREACH: aggregated total >= $10k, nothing reported
                    finding = RuleFinding(
                        finding_id=str(uuid.uuid4()),
                        run_id=self.run_id,
                        rule_id="",
                        rule_code="FINTRAC_24HR_AGGREGATION",
                        rule_version=1,
                        transaction_id=",".join(tx_ids[:5]),  # first 5 IDs
                        severity="BREACH",
                        detail={
                            "party_id": party_id,
                            "direction": direction,
                            "value_date": str(value_date),
                            "total_cad_amount": str(total_cad),
                            "transaction_count": len(tx_ids),
                            "transaction_ids": tx_ids,
                            "reported_count": 0,
                            "reason": f"Aggregated EFTs of CAD {total_cad} within 24h window not reported",
                        },
                    )
                    self.session.add(finding)
                    breach_count += 1
            else:
                # Total below $10k but individual transactions were reported → over-reporting
                if reported_in_group:
                    finding = RuleFinding(
                        finding_id=str(uuid.uuid4()),
                        run_id=self.run_id,
                        rule_id="",
                        rule_code="FINTRAC_OVER_REPORTING",
                        rule_version=1,
                        transaction_id=",".join(reported_in_group[:5]),
                        severity="INFO",
                        detail={
                            "party_id": party_id,
                            "direction": direction,
                            "value_date": str(value_date),
                            "total_cad_amount": str(total_cad),
                            "reason": "Aggregated EFTs below $10,000 threshold were reported",
                        },
                    )
                    self.session.add(finding)
                    over_report_count += 1

        self.session.commit()
        return {
            "aggregation_groups": group_count,
            "breaches": breach_count,
            "over_reporting": over_report_count,
        }
