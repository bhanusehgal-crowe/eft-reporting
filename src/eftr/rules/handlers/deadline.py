from datetime import date

import pandas as pd

from config.settings import settings
from src.eftr.utils.business_days import deadline_breached


def evaluate(eft_df: pd.DataFrame, rep_df: pd.DataFrame, rule: dict) -> list[dict]:
    """
    FINTRAC_FILING_DEADLINE: EFTR filed > 5 business days after transaction.
    Returns list of finding dicts.
    """
    max_days = rule.get("parameters", {}).get("max_business_days", 5)
    province = settings.default_province
    findings = []

    if rep_df.empty or eft_df.empty:
        return findings

    # Build map: reported_transaction_id → report_date
    rep_map = {}
    for _, row in rep_df.iterrows():
        tid = str(row.get("reported_transaction_id", ""))
        try:
            rep_map[tid] = pd.to_datetime(row["report_date"]).date()
        except Exception:
            pass

    for _, row in eft_df.iterrows():
        tx_id = str(row.get("transaction_id", ""))
        if tx_id not in rep_map:
            continue

        try:
            tx_date = pd.to_datetime(row["value_date"]).date()
        except Exception:
            continue

        filing_date = rep_map[tx_id]
        if deadline_breached(tx_date, filing_date, max_days, province):
            findings.append(
                {
                    "rule_code": rule["rule_code"],
                    "rule_id": rule.get("rule_id", ""),
                    "rule_version": rule.get("version", 1),
                    "transaction_id": tx_id,
                    "severity": rule["severity"],
                    "detail": {
                        "transaction_date": str(tx_date),
                        "filing_date": str(filing_date),
                        "max_business_days": max_days,
                        "reason": f"EFTR filed on {filing_date}, which is > {max_days} business days after transaction on {tx_date}",
                    },
                }
            )

    return findings
