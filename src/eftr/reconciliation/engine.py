import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.reconciliation import ReconciliationResult
from src.eftr.models.rule import RuleFinding
from src.eftr.reconciliation.matchers import exact_id_match, fuzzy_match
from src.eftr.utils.snapshot import load_parquet, save_parquet

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


class ReconciliationEngine:
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
            component="reconciliation_engine",
            operator_id=self.operator_id,
            message=message,
            detail=detail or {},
            created_at=datetime.utcnow(),
        )
        self.session.add(entry)

    def _load_snapshots(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        eft_path = Path(settings.data_processed_dir) / "eft" / f"{self.run_id}_eft.parquet"
        rep_path = (
            Path(settings.data_processed_dir) / "reported" / f"{self.run_id}_reported.parquet"
        )
        eft_df = load_parquet(eft_path) if eft_path.exists() else pd.DataFrame()
        rep_df = load_parquet(rep_path) if rep_path.exists() else pd.DataFrame()
        return eft_df, rep_df

    def _persist_result(
        self,
        status: str,
        match_method: str | None,
        eft_id: str | None,
        rep_id: str | None,
        variance: Decimal | None,
        detail: dict,
    ):
        result = ReconciliationResult(
            result_id=str(uuid.uuid4()),
            run_id=self.run_id,
            eft_transaction_id=eft_id,
            reported_id=rep_id,
            status=status,
            match_method=match_method,
            variance_amount=variance,
            detail=detail,
        )
        self.session.add(result)

    def _persist_breach_finding(self, rule_code: str, transaction_id: str, detail: dict):
        finding = RuleFinding(
            finding_id=str(uuid.uuid4()),
            run_id=self.run_id,
            rule_id="",
            rule_code=rule_code,
            rule_version=1,
            transaction_id=transaction_id,
            severity="BREACH",
            detail=detail,
        )
        self.session.add(finding)

    def run(self) -> dict:
        self._audit("RECONCILIATION_STARTED", "INFO", "Starting reconciliation")
        eft_df, rep_df = self._load_snapshots()

        if eft_df.empty and rep_df.empty:
            self._audit("RECONCILIATION_SKIPPED", "WARN", "No EFT or reported data found for run")
            self.session.commit()
            return {"matched": 0, "missed": 0, "phantom": 0, "breaches": 0}

        if eft_df.empty:
            # No EFTs — all reported transactions are phantom
            phantom_count = 0
            for _, row in rep_df.iterrows():
                rep_id = str(row.get("reported_id", ""))
                self._persist_result(
                    "PHANTOM", None, None, rep_id, None,
                    {"reason": "Reported transaction has no matching EFT"}
                )
                phantom_count += 1
            self._audit(
                "RECONCILIATION_COMPLETE", "INFO",
                f"No EFT data; {phantom_count} phantom reported transactions",
                {"matched": 0, "missed": 0, "phantom": phantom_count, "breaches": 0},
            )
            self.session.commit()
            return {"matched": 0, "missed": 0, "phantom": phantom_count, "breaches": 0}

        # Ensure string types for join keys
        eft_df["transaction_id"] = eft_df["transaction_id"].astype(str)
        if not rep_df.empty:
            rep_df["reported_transaction_id"] = rep_df["reported_transaction_id"].astype(str)

        # Tier 1: Exact match
        if not rep_df.empty:
            tier1_matched, unmatched_eft, unmatched_rep = exact_id_match(eft_df, rep_df)
        else:
            tier1_matched = pd.DataFrame()
            unmatched_eft = eft_df.copy()
            unmatched_rep = pd.DataFrame()

        matched_count = 0
        # Persist tier-1 matches
        for _, row in tier1_matched.iterrows():
            self._persist_result(
                "MATCHED",
                "EXACT_ID",
                str(row["transaction_id"]),
                str(row.get("reported_id", "")),
                None,
                {"match_method": "EXACT_ID"},
            )
            matched_count += 1

        # Tier 2: Fuzzy match on remaining
        if not unmatched_eft.empty and not unmatched_rep.empty:
            tier2_matched, remaining_eft, remaining_rep = fuzzy_match(unmatched_eft, unmatched_rep)
        else:
            tier2_matched = pd.DataFrame()
            remaining_eft = unmatched_eft
            remaining_rep = unmatched_rep if not rep_df.empty else pd.DataFrame()

        for _, row in tier2_matched.iterrows():
            self._persist_result(
                "MATCHED",
                "FUZZY_AMOUNT_DATE",
                str(row.get("transaction_id", "")),
                str(row.get("reported_id_rep", "")),
                None,
                {"match_method": "FUZZY_AMOUNT_DATE"},
            )
            matched_count += 1

        # MISSED: EFTs not in any reported set
        missed_count = 0
        breach_count = 0
        for _, row in remaining_eft.iterrows():
            eft_id = str(row["transaction_id"])
            self._persist_result("MISSED", None, eft_id, None, None, {"reason": "No matching EFTR found"})
            missed_count += 1

            # FINTRAC threshold breach check
            try:
                cad_amount = Decimal(str(row.get("cad_amount", 0)))
            except Exception:
                cad_amount = Decimal("0")

            if cad_amount >= FINTRAC_THRESHOLD_CAD:
                self._persist_breach_finding(
                    "FINTRAC_SINGLE_THRESHOLD",
                    eft_id,
                    {
                        "cad_amount": str(cad_amount),
                        "value_date": str(row.get("value_date", "")),
                        "reason": f"EFT of CAD {cad_amount} >= $10,000 has no corresponding EFTR",
                    },
                )
                breach_count += 1

        # PHANTOM: Reported with no matching EFT
        phantom_count = 0
        for _, row in remaining_rep.iterrows():
            rep_id = str(row.get("reported_id", ""))
            self._persist_result(
                "PHANTOM", None, None, rep_id, None, {"reason": "Reported transaction has no matching EFT"}
            )
            phantom_count += 1

        self._audit(
            "RECONCILIATION_COMPLETE",
            "INFO",
            f"Reconciliation complete: matched={matched_count}, missed={missed_count}, phantom={phantom_count}, breaches={breach_count}",
            {
                "matched": matched_count,
                "missed": missed_count,
                "phantom": phantom_count,
                "breaches": breach_count,
            },
        )
        self.session.commit()
        return {
            "matched": matched_count,
            "missed": missed_count,
            "phantom": phantom_count,
            "breaches": breach_count,
        }
