"""FINTRAC_FILING_DEADLINE rule handler — pandas-free."""
from datetime import date

from config.settings import settings
from src.eftr.utils.business_days import deadline_breached


def _parse_date(v) -> date | None:
    if not v or str(v).strip() in ("", "None", "nan"):
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def evaluate(eft_rows: list[dict], rep_rows: list[dict], reported_ids: set, rule: dict) -> list[dict]:
    max_days = rule.get("parameters", {}).get("max_business_days", 5)
    province = settings.default_province
    findings = []

    if not rep_rows or not eft_rows:
        return findings

    rep_map = {}
    for row in rep_rows:
        tid = str(row.get("reported_transaction_id", ""))
        d = _parse_date(row.get("report_date"))
        if tid and d:
            rep_map[tid] = d

    for row in eft_rows:
        tx_id = str(row.get("transaction_id", ""))
        if tx_id not in rep_map:
            continue
        tx_date = _parse_date(row.get("value_date"))
        if not tx_date:
            continue
        filing_date = rep_map[tx_id]
        if deadline_breached(tx_date, filing_date, max_days, province):
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": tx_id,
                "severity": rule["severity"],
                "detail": {
                    "transaction_date": str(tx_date),
                    "filing_date": str(filing_date),
                    "max_business_days": max_days,
                    "reason": f"EFTR filed {filing_date}, > {max_days} business days after transaction {tx_date}",
                },
            })
    return findings
