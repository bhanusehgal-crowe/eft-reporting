"""FINTRAC_SINGLE_THRESHOLD rule handler — pandas-free."""
from decimal import Decimal

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


def evaluate(eft_rows: list[dict], rep_rows: list[dict], reported_ids: set, rule: dict) -> list[dict]:
    threshold = Decimal(str(rule.get("parameters", {}).get("threshold_cad", 10000)))
    findings = []
    for row in eft_rows:
        tx_id = str(row.get("transaction_id", ""))
        try:
            cad = Decimal(str(row.get("cad_amount") or 0))
        except Exception:
            cad = Decimal("0")
        if cad >= threshold and tx_id not in reported_ids:
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": tx_id,
                "severity": rule["severity"],
                "detail": {
                    "cad_amount": str(cad),
                    "threshold_cad": str(threshold),
                    "value_date": str(row.get("value_date", "")),
                    "direction": str(row.get("direction", "")),
                    "originator_name": str(row.get("originator_name", "")),
                    "beneficiary_name": str(row.get("beneficiary_name", "")),
                    "reason": f"EFT of CAD {cad} >= ${threshold} has no corresponding EFTR",
                },
            })
    return findings
