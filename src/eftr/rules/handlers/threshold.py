from decimal import Decimal

import pandas as pd

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


def evaluate(eft_df: pd.DataFrame, reported_ids: set, rule: dict) -> list[dict]:
    """
    FINTRAC_SINGLE_THRESHOLD: single international EFT >= CAD $10,000 not reported.
    Returns list of finding dicts.
    """
    threshold = Decimal(str(rule.get("parameters", {}).get("threshold_cad", 10000)))
    findings = []

    for _, row in eft_df.iterrows():
        tx_id = str(row.get("transaction_id", ""))
        try:
            cad_amount = Decimal(str(row.get("cad_amount", 0)))
        except Exception:
            cad_amount = Decimal("0")

        if cad_amount >= threshold and tx_id not in reported_ids:
            findings.append(
                {
                    "rule_code": rule["rule_code"],
                    "rule_id": rule.get("rule_id", ""),
                    "rule_version": rule.get("version", 1),
                    "transaction_id": tx_id,
                    "severity": rule["severity"],
                    "detail": {
                        "cad_amount": str(cad_amount),
                        "threshold_cad": str(threshold),
                        "value_date": str(row.get("value_date", "")),
                        "direction": str(row.get("direction", "")),
                        "originator_name": str(row.get("originator_name", "")),
                        "beneficiary_name": str(row.get("beneficiary_name", "")),
                        "reason": f"EFT of CAD {cad_amount} >= threshold CAD {threshold} not reported",
                    },
                }
            )

    return findings
