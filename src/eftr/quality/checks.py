"""Data quality checks — pandas-free."""
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from src.eftr.models.audit_log import AuditLog

ISO_4217_SAMPLE = {
    "CAD", "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "HKD", "SGD", "CNY",
    "MXN", "BRL", "INR", "KRW", "SEK", "NOK", "DKK", "NZD", "ZAR", "RUB",
}
FAILURE_THRESHOLD = 0.05


class QualityCheckResult:
    def __init__(self, check_name, passed, fail_count, total, detail):
        self.check_name, self.passed = check_name, passed
        self.fail_count, self.total, self.detail = fail_count, total, detail


def _to_float(v) -> float | None:
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def check_eft_quality(rows: list[dict]) -> list[QualityCheckResult]:
    results = []
    total = len(rows)
    if not rows:
        return results
    required = ["transaction_id", "value_date", "amount", "currency_code", "direction",
                "originator_name", "beneficiary_name"]
    missing_cols = [c for c in required if c not in rows[0]]
    results.append(QualityCheckResult("mandatory_columns_present", not missing_cols,
                                      len(missing_cols), len(required),
                                      f"Missing: {missing_cols}" if missing_cols else "All present"))
    if missing_cols:
        return results

    bad_amount = sum(1 for r in rows if (_to_float(r.get("amount")) or 0) <= 0)
    results.append(QualityCheckResult("amount_positive", bad_amount == 0, bad_amount, total,
                                      f"{bad_amount} rows with amount <= 0"))

    bad_currency = sum(1 for r in rows if str(r.get("currency_code", "")).upper() not in ISO_4217_SAMPLE)
    results.append(QualityCheckResult("currency_code_valid", bad_currency == 0, bad_currency, total,
                                      f"{bad_currency} rows with unrecognized currency"))

    today = date.today()
    future = 0
    for r in rows:
        try:
            if date.fromisoformat(str(r.get("value_date", ""))[:10]) > today:
                future += 1
        except ValueError:
            pass
    results.append(QualityCheckResult("value_date_not_future", future == 0, future, total,
                                      f"{future} rows with future value_date"))

    bad_dir = sum(1 for r in rows if str(r.get("direction", "")).upper() not in {"INITIATION", "RECEIPT"})
    results.append(QualityCheckResult("direction_valid", bad_dir == 0, bad_dir, total,
                                      f"{bad_dir} rows with invalid direction"))
    return results


def check_reported_quality(rows: list[dict]) -> list[QualityCheckResult]:
    results = []
    total = len(rows)
    if not rows:
        return results
    required = ["report_reference", "reporting_entity_id", "reported_transaction_id",
                "report_date", "reported_amount", "reported_currency", "direction"]
    missing_cols = [c for c in required if c not in rows[0]]
    results.append(QualityCheckResult("mandatory_columns_present", not missing_cols,
                                      len(missing_cols), len(required),
                                      f"Missing: {missing_cols}" if missing_cols else "All present"))
    if missing_cols:
        return results
    bad = sum(1 for r in rows if (_to_float(r.get("reported_amount")) or 0) <= 0)
    results.append(QualityCheckResult("reported_amount_positive", bad == 0, bad, total, f"{bad} rows <= 0"))
    return results


def run_quality_checks(eft_rows: list[dict], rep_rows: list[dict],
                       session: Session, run_id: str, operator_id: str) -> bool:
    all_passed = True
    for feed, rows, fn in [("EFT", eft_rows, check_eft_quality), ("Reported", rep_rows, check_reported_quality)]:
        if not rows:
            continue
        for r in fn(rows):
            fail_rate = r.fail_count / max(len(rows), 1)
            severity = "INFO" if r.passed else "WARN"
            session.add(AuditLog(
                log_id=str(uuid.uuid4()), run_id=run_id, event_type="QUALITY_CHECK",
                severity=severity, component="quality_checks", operator_id=operator_id,
                message=f"[{feed}] {r.check_name}: {'PASS' if r.passed else 'FAIL'} — {r.detail}",
                detail={"feed": feed, "check": r.check_name, "passed": r.passed,
                        "fail_count": r.fail_count, "total": r.total},
                created_at=datetime.utcnow(),
            ))
            if not r.passed and fail_rate >= FAILURE_THRESHOLD:
                all_passed = False
    session.commit()
    return all_passed
