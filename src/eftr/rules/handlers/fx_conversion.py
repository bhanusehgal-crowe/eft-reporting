"""FINTRAC_FX_CONVERSION rule handler — pandas-free."""


def evaluate(eft_rows: list[dict], rep_rows: list[dict], rule: dict) -> list[dict]:
    findings = []
    for row in eft_rows:
        currency = str(row.get("currency_code") or "").upper()
        if currency == "CAD":
            continue
        rate = row.get("cad_conversion_rate")
        if not rate or str(rate).strip() in ("", "None", "nan"):
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": str(row.get("transaction_id", "")),
                "severity": rule["severity"],
                "detail": {
                    "currency_code": currency,
                    "reason": f"Foreign currency {currency} EFT has no BoC conversion rate recorded",
                },
            })
    return findings
