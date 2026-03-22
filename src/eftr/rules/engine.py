import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.rule import RuleFinding
from src.eftr.rules.loader import load_active_rules
from src.eftr.rules.registry import RULE_REGISTRY
from src.eftr.utils.snapshot import load_parquet


class RulesEngine:
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
            component="rules_engine",
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

    def run(self) -> dict:
        self._audit("RULES_EVALUATION_STARTED", "INFO", "Starting rules evaluation")
        eft_df, rep_df = self._load_data()

        if eft_df.empty:
            self._audit("RULES_EVALUATION_SKIPPED", "WARN", "No EFT data for rules evaluation")
            self.session.commit()
            return {"rules_evaluated": 0, "findings": 0}

        active_rules = load_active_rules(self.session)
        if not active_rules:
            self._audit("RULES_EVALUATION_SKIPPED", "WARN", "No active rules found")
            self.session.commit()
            return {"rules_evaluated": 0, "findings": 0}

        # Build set of reported transaction IDs
        reported_ids: set[str] = set()
        if not rep_df.empty and "reported_transaction_id" in rep_df.columns:
            reported_ids = set(rep_df["reported_transaction_id"].astype(str))

        total_findings = 0
        for rule in active_rules:
            rule_code = rule["rule_code"]
            handler = RULE_REGISTRY.get(rule_code)
            if not handler:
                continue

            try:
                findings = handler(eft_df, rep_df, reported_ids, rule)
            except Exception as exc:
                self._audit(
                    "RULE_EVALUATION_ERROR",
                    "WARN",
                    f"Rule {rule_code} evaluation failed: {exc}",
                    {"rule_code": rule_code, "error": str(exc)},
                )
                continue

            for f in findings:
                finding = RuleFinding(
                    finding_id=str(uuid.uuid4()),
                    run_id=self.run_id,
                    rule_id=f.get("rule_id", ""),
                    rule_code=f["rule_code"],
                    rule_version=f.get("rule_version", 1),
                    transaction_id=f.get("transaction_id"),
                    severity=f["severity"],
                    detail=f.get("detail", {}),
                )
                self.session.add(finding)
                total_findings += 1

        self._audit(
            "RULES_EVALUATION_COMPLETE",
            "INFO",
            f"Rules evaluation complete: {len(active_rules)} rules, {total_findings} findings",
            {"rules_evaluated": len(active_rules), "findings": total_findings},
        )
        self.session.commit()
        return {"rules_evaluated": len(active_rules), "findings": total_findings}
