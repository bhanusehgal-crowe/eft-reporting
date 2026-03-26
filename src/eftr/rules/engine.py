"""Rules engine — pandas-free."""
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.rule import RuleFinding
from src.eftr.rules.loader import load_active_rules
from src.eftr.rules.registry import RULE_REGISTRY
from src.eftr.utils.snapshot import load_snapshot


class RulesEngine:
    def __init__(self, session: Session, run_id: str, operator_id: str):
        self.session = session
        self.run_id = run_id
        self.operator_id = operator_id

    def _audit(self, event_type: str, severity: str, message: str, detail: dict | None = None):
        self.session.add(AuditLog(
            log_id=str(uuid.uuid4()), run_id=self.run_id, event_type=event_type,
            severity=severity, component="rules_engine", operator_id=self.operator_id,
            message=message, detail=detail or {}, created_at=datetime.utcnow(),
        ))

    def _load_data(self) -> tuple[list[dict], list[dict]]:
        eft_path = Path(settings.data_processed_dir) / "eft" / f"{self.run_id}_eft.csv"
        rep_path = Path(settings.data_processed_dir) / "reported" / f"{self.run_id}_reported.csv"
        return load_snapshot(eft_path), load_snapshot(rep_path)

    def run(self) -> dict:
        self._audit("RULES_EVALUATION_STARTED", "INFO", "Starting rules evaluation")
        eft_rows, rep_rows = self._load_data()

        if not eft_rows:
            self._audit("RULES_EVALUATION_SKIPPED", "WARN", "No EFT data for rules evaluation")
            self.session.commit()
            return {"rules_evaluated": 0, "findings": 0}

        active_rules = load_active_rules(self.session)
        if not active_rules:
            self._audit("RULES_EVALUATION_SKIPPED", "WARN", "No active rules found")
            self.session.commit()
            return {"rules_evaluated": 0, "findings": 0}

        reported_ids = {str(r.get("reported_transaction_id", "")) for r in rep_rows}

        total_findings = 0
        for rule in active_rules:
            rule_code = rule["rule_code"]
            handler = RULE_REGISTRY.get(rule_code)
            if not handler:
                continue
            try:
                findings = handler(eft_rows, rep_rows, reported_ids, rule)
            except Exception as exc:
                self._audit("RULE_EVALUATION_ERROR", "WARN",
                            f"Rule {rule_code} failed: {exc}",
                            {"rule_code": rule_code, "error": str(exc)})
                continue

            for f in findings:
                self.session.add(RuleFinding(
                    finding_id=str(uuid.uuid4()), run_id=self.run_id,
                    rule_id=f.get("rule_id", ""), rule_code=f["rule_code"],
                    rule_version=f.get("rule_version", 1), transaction_id=f.get("transaction_id"),
                    severity=f["severity"], detail=f.get("detail", {}),
                ))
                total_findings += 1

        self._audit("RULES_EVALUATION_COMPLETE", "INFO",
                    f"{len(active_rules)} rules, {total_findings} findings",
                    {"rules_evaluated": len(active_rules), "findings": total_findings})
        self.session.commit()
        return {"rules_evaluated": len(active_rules), "findings": total_findings}
