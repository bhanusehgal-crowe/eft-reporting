"""FINTRAC_OVER_REPORTING rule handler — pandas-free."""
from decimal import Decimal

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


def evaluate(eft_rows: list[dict], reported_ids: set, rule: dict) -> list[dict]:
    threshold = Decimal(str(rule.get("parameters", {}).get("threshold_cad", 10000)))
    findings = []
    for row in eft_rows:
        tx_id = str(row.get("transaction_id", ""))
        if tx_id not in reported_ids:
            continue
        try:
            cad = Decimal(str(row.get("cad_amount") or 0))
        except Exception:
            cad = Decimal("0")
        if cad < threshold:
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": tx_id,
                "severity": rule["severity"],
                "detail": {
                    "cad_amount": str(cad),
                    "threshold_cad": str(threshold),
                    "reason": f"EFT of CAD {cad} is below CAD {threshold} threshold but was reported",
                },
            })
    return findings
