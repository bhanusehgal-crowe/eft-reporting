import pandas as pd

TRAVEL_RULE_FIELDS = ["originator_name", "originator_address", "originator_account",
                      "beneficiary_name", "beneficiary_address", "beneficiary_account"]


def evaluate_mandatory_fields(eft_df: pd.DataFrame, rule: dict) -> list[dict]:
    """
    FINTRAC_MANDATORY_FIELDS: Required FINTRAC fields missing from EFT record.
    """
    required = rule.get("parameters", {}).get(
        "required_fields",
        ["transaction_id", "value_date", "amount", "currency_code", "direction",
         "originator_name", "beneficiary_name"]
    )
    findings = []
    for _, row in eft_df.iterrows():
        missing = [f for f in required if not row.get(f) or str(row.get(f, "")).strip() == ""]
        if missing:
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": str(row.get("transaction_id", "")),
                "severity": rule["severity"],
                "detail": {
                    "missing_fields": missing,
                    "reason": f"Required fields missing: {', '.join(missing)}",
                },
            })
    return findings


def evaluate_travel_rule(eft_df: pd.DataFrame, rule: dict) -> list[dict]:
    """
    FINTRAC_TRAVEL_RULE: Originator or beneficiary info missing from international EFT.
    """
    findings = []
    for _, row in eft_df.iterrows():
        missing = [f for f in TRAVEL_RULE_FIELDS if not row.get(f) or str(row.get(f, "")).strip() == ""]
        if missing:
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": str(row.get("transaction_id", "")),
                "severity": rule["severity"],
                "detail": {
                    "missing_fields": missing,
                    "reason": f"Travel rule fields missing: {', '.join(missing)}",
                },
            })
    return findings
