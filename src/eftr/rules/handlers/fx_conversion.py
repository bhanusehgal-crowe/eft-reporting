from decimal import Decimal

import pandas as pd


def evaluate(eft_df: pd.DataFrame, rep_df: pd.DataFrame, rule: dict) -> list[dict]:
    """
    FINTRAC_FX_CONVERSION: Reported CAD amount differs from BoC-derived amount by > tolerance.
    This is a placeholder check — full reperformance happens in Phase 2.
    Checks if currency != CAD and no cad_conversion_rate is set.
    """
    tolerance_pct = rule.get("parameters", {}).get("tolerance_pct", 0.01)
    findings = []

    for _, row in eft_df.iterrows():
        currency = str(row.get("currency_code", "")).upper()
        if currency == "CAD":
            continue

        cad_conversion_rate = row.get("cad_conversion_rate")
        if not cad_conversion_rate or str(cad_conversion_rate).strip() in ("", "None", "nan"):
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": str(row.get("transaction_id", "")),
                "severity": rule["severity"],
                "detail": {
                    "currency_code": currency,
                    "cad_conversion_rate": str(cad_conversion_rate),
                    "reason": f"Foreign currency {currency} EFT has no BoC conversion rate recorded",
                },
            })

    return findings
