"""Reconciliation engine — pandas-free."""
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.reconciliation import ReconciliationResult
from src.eftr.models.rule import RuleFinding
from src.eftr.reconciliation.matchers import exact_id_match, fuzzy_match
from src.eftr.utils.snapshot import load_snapshot

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


class ReconciliationEngine:
    def __init__(self, session: Session, run_id: str, operator_id: str):
        self.session = session
        self.run_id = run_id
        self.operator_id = operator_id

    def _audit(self, event_type: str, severity: str, message: str, detail: dict | None = None):
        self.session.add(AuditLog(
            log_id=str(uuid.uuid4()), run_id=self.run_id, event_type=event_type,
            severity=severity, component="reconciliation_engine", operator_id=self.operator_id,
            message=message, detail=detail or {}, created_at=datetime.utcnow(),
        ))

    def _load_snapshots(self) -> tuple[list[dict], list[dict]]:
        eft_path = Path(settings.data_processed_dir) / "eft" / f"{self.run_id}_eft.csv"
        rep_path = Path(settings.data_processed_dir) / "reported" / f"{self.run_id}_reported.csv"
        return load_snapshot(eft_path), load_snapshot(rep_path)

    def _persist_result(self, status, match_method, eft_id, rep_id, variance, detail):
        self.session.add(ReconciliationResult(
            result_id=str(uuid.uuid4()), run_id=self.run_id,
            eft_transaction_id=eft_id, reported_id=rep_id,
            status=status, match_method=match_method, variance_amount=variance, detail=detail,
        ))

    def _persist_breach(self, rule_code, transaction_id, detail):
        self.session.add(RuleFinding(
            finding_id=str(uuid.uuid4()), run_id=self.run_id, rule_id="",
            rule_code=rule_code, rule_version=1, transaction_id=transaction_id,
            severity="BREACH", detail=detail,
        ))

    def run(self) -> dict:
        self._audit("RECONCILIATION_STARTED", "INFO", "Starting reconciliation")
        eft_rows, rep_rows = self._load_snapshots()

        if not eft_rows and not rep_rows:
            self._audit("RECONCILIATION_SKIPPED", "WARN", "No data found for run")
            self.session.commit()
            return {"matched": 0, "missed": 0, "phantom": 0, "breaches": 0}

        if not eft_rows:
            for rep in rep_rows:
                self._persist_result("PHANTOM", None, None, str(rep.get("reported_id", "")),
                                     None, {"reason": "Reported transaction has no matching EFT"})
            self.session.commit()
            return {"matched": 0, "missed": 0, "phantom": len(rep_rows), "breaches": 0}

        # Tier 1: exact match
        if rep_rows:
            t1_matched, unmatched_eft, unmatched_rep = exact_id_match(eft_rows, rep_rows)
        else:
            t1_matched, unmatched_eft, unmatched_rep = [], list(eft_rows), []

        matched_count = 0
        for row in t1_matched:
            self._persist_result("MATCHED", "EXACT_ID",
                                 str(row.get("transaction_id", "")),
                                 str(row.get("reported_id_rep", "")), None, {"match_method": "EXACT_ID"})
            matched_count += 1

        # Tier 2: fuzzy match
        if unmatched_eft and unmatched_rep:
            t2_matched, remaining_eft, remaining_rep = fuzzy_match(unmatched_eft, unmatched_rep)
        else:
            t2_matched, remaining_eft, remaining_rep = [], unmatched_eft, unmatched_rep

        for row in t2_matched:
            self._persist_result("MATCHED", "FUZZY_AMOUNT_DATE",
                                 str(row.get("transaction_id", "")),
                                 str(row.get("reported_id_rep", "")), None, {"match_method": "FUZZY_AMOUNT_DATE"})
            matched_count += 1

        # MISSED + threshold breach
        missed_count = breach_count = 0
        for row in remaining_eft:
            eft_id = str(row.get("transaction_id", ""))
            self._persist_result("MISSED", None, eft_id, None, None, {"reason": "No matching EFTR found"})
            missed_count += 1
            try:
                cad = Decimal(str(row.get("cad_amount") or 0))
            except Exception:
                cad = Decimal("0")
            if cad >= FINTRAC_THRESHOLD_CAD:
                self._persist_breach("FINTRAC_SINGLE_THRESHOLD", eft_id, {
                    "cad_amount": str(cad),
                    "value_date": str(row.get("value_date", "")),
                    "direction": str(row.get("direction", "")),
                    "reason": f"EFT of CAD {cad} >= $10,000 has no corresponding EFTR",
                })
                breach_count += 1

        # PHANTOM
        phantom_count = 0
        for rep in remaining_rep:
            self._persist_result("PHANTOM", None, None, str(rep.get("reported_id", "")),
                                 None, {"reason": "Reported transaction has no matching EFT"})
            phantom_count += 1

        self._audit("RECONCILIATION_COMPLETE", "INFO",
                    f"matched={matched_count}, missed={missed_count}, phantom={phantom_count}",
                    {"matched": matched_count, "missed": missed_count,
                     "phantom": phantom_count, "breaches": breach_count})
        self.session.commit()
        return {"matched": matched_count, "missed": missed_count,
                "phantom": phantom_count, "breaches": breach_count}
