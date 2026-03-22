"""Data quality checks for EFT and Reported feeds."""
import uuid
from datetime import date, datetime

import pandas as pd
from sqlalchemy.orm import Session

from src.eftr.models.audit_log import AuditLog

ISO_4217_SAMPLE = {
    "CAD", "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "HKD", "SGD", "CNY",
    "MXN", "BRL", "INR", "KRW", "SEK", "NOK", "DKK", "NZD", "ZAR", "RUB",
}

FAILURE_THRESHOLD = 0.05  # 5% bad rows halts pipeline


class QualityCheckResult:
    def __init__(self, check_name: str, passed: bool, fail_count: int, total: int, detail: str):
        self.check_name = check_name
        self.passed = passed
        self.fail_count = fail_count
        self.total = total
        self.detail = detail


def check_eft_quality(df: pd.DataFrame) -> list[QualityCheckResult]:
    results = []
    total = len(df)

    # 1. Mandatory columns present
    required_cols = ["transaction_id", "value_date", "amount", "currency_code", "direction",
                     "originator_name", "beneficiary_name"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    results.append(QualityCheckResult(
        "mandatory_columns_present",
        len(missing_cols) == 0,
        len(missing_cols),
        len(required_cols),
        f"Missing columns: {missing_cols}" if missing_cols else "All mandatory columns present",
    ))

    if missing_cols:
        return results  # Can't proceed without required columns

    # 2. amount > 0
    bad_amount = df[pd.to_numeric(df["amount"], errors="coerce").fillna(0) <= 0]
    results.append(QualityCheckResult(
        "amount_positive", len(bad_amount) == 0, len(bad_amount), total,
        f"{len(bad_amount)} rows with amount <= 0",
    ))

    # 3. currency_code in ISO 4217 (sample set)
    bad_currency = df[~df["currency_code"].str.upper().isin(ISO_4217_SAMPLE)]
    results.append(QualityCheckResult(
        "currency_code_valid", len(bad_currency) == 0, len(bad_currency), total,
        f"{len(bad_currency)} rows with unrecognized currency_code",
    ))

    # 4. value_date not in future
    try:
        today = date.today()
        df_dates = pd.to_datetime(df["value_date"], errors="coerce")
        future_dates = df[df_dates.dt.date > today]
        results.append(QualityCheckResult(
            "value_date_not_future", len(future_dates) == 0, len(future_dates), total,
            f"{len(future_dates)} rows with future value_date",
        ))
    except Exception as e:
        results.append(QualityCheckResult("value_date_not_future", False, 0, total, str(e)))

    # 5. direction in allowed values
    allowed_directions = {"INITIATION", "RECEIPT"}
    bad_direction = df[~df["direction"].str.upper().isin(allowed_directions)]
    results.append(QualityCheckResult(
        "direction_valid", len(bad_direction) == 0, len(bad_direction), total,
        f"{len(bad_direction)} rows with invalid direction",
    ))

    return results


def check_reported_quality(df: pd.DataFrame) -> list[QualityCheckResult]:
    results = []
    total = len(df)

    required_cols = ["report_reference", "reporting_entity_id", "reported_transaction_id",
                     "report_date", "reported_amount", "reported_currency", "direction"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    results.append(QualityCheckResult(
        "mandatory_columns_present",
        len(missing_cols) == 0,
        len(missing_cols),
        len(required_cols),
        f"Missing columns: {missing_cols}" if missing_cols else "All mandatory columns present",
    ))

    if missing_cols or total == 0:
        return results

    # reported_amount > 0
    bad_amount = df[pd.to_numeric(df["reported_amount"], errors="coerce").fillna(0) <= 0]
    results.append(QualityCheckResult(
        "reported_amount_positive", len(bad_amount) == 0, len(bad_amount), total,
        f"{len(bad_amount)} rows with reported_amount <= 0",
    ))

    # report_reference non-null
    bad_ref = df[df["report_reference"].isna() | (df["report_reference"].astype(str).str.strip() == "")]
    results.append(QualityCheckResult(
        "report_reference_non_null", len(bad_ref) == 0, len(bad_ref), total,
        f"{len(bad_ref)} rows with null/empty report_reference",
    ))

    return results


def run_quality_checks(
    eft_df: pd.DataFrame,
    rep_df: pd.DataFrame,
    session: Session,
    run_id: str,
    operator_id: str,
) -> bool:
    """Run all quality checks. Returns False if pipeline should halt."""
    all_passed = True

    for feed_name, df, check_fn in [
        ("EFT", eft_df, check_eft_quality),
        ("Reported", rep_df, check_reported_quality),
    ]:
        if df.empty:
            continue
        results = check_fn(df)
        total = len(df)
        for r in results:
            fail_rate = r.fail_count / max(total, 1)
            severity = "INFO" if r.passed else ("WARN" if fail_rate < FAILURE_THRESHOLD else "ERROR")

            entry = AuditLog(
                log_id=str(uuid.uuid4()),
                run_id=run_id,
                event_type="QUALITY_CHECK",
                severity=severity if severity != "ERROR" else "WARN",
                component="quality_checks",
                operator_id=operator_id,
                message=f"[{feed_name}] {r.check_name}: {'PASS' if r.passed else 'FAIL'} — {r.detail}",
                detail={
                    "feed": feed_name,
                    "check": r.check_name,
                    "passed": r.passed,
                    "fail_count": r.fail_count,
                    "total": r.total,
                },
                created_at=datetime.utcnow(),
            )
            session.add(entry)

            if not r.passed and fail_rate >= FAILURE_THRESHOLD:
                halt_entry = AuditLog(
                    log_id=str(uuid.uuid4()),
                    run_id=run_id,
                    event_type="PIPELINE_HALTED",
                    severity="ERROR",
                    component="quality_checks",
                    operator_id=operator_id,
                    message=f"Pipeline halted: [{feed_name}] {r.check_name} failure rate {fail_rate:.1%} exceeds threshold {FAILURE_THRESHOLD:.1%}",
                    detail={"feed": feed_name, "check": r.check_name, "fail_rate": fail_rate},
                    created_at=datetime.utcnow(),
                )
                session.add(halt_entry)
                all_passed = False

    session.commit()
    return all_passed
