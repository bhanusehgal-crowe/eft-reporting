from decimal import Decimal

import pandas as pd

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


def evaluate(eft_df: pd.DataFrame, reported_ids: set, rule: dict) -> list[dict]:
    """
    FINTRAC_OVER_REPORTING: EFTR submitted for EFT below $10,000 CAD threshold.
    """
    threshold = Decimal(str(rule.get("parameters", {}).get("threshold_cad", 10000)))
    findings = []

    for _, row in eft_df.iterrows():
        tx_id = str(row.get("transaction_id", ""))
        if tx_id not in reported_ids:
            continue

        try:
            cad_amount = Decimal(str(row.get("cad_amount", 0)))
        except Exception:
            cad_amount = Decimal("0")

        if cad_amount < threshold:
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": tx_id,
                "severity": rule["severity"],
                "detail": {
                    "cad_amount": str(cad_amount),
                    "threshold_cad": str(threshold),
                    "reason": f"EFT of CAD {cad_amount} is below CAD {threshold} threshold but was reported",
                },
            })

    return findings
