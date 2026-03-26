"""FINTRAC_MANDATORY_FIELDS and FINTRAC_TRAVEL_RULE handlers — pandas-free."""

TRAVEL_RULE_FIELDS = [
    "originator_name", "originator_address", "originator_account",
    "beneficiary_name", "beneficiary_address", "beneficiary_account",
]


def _missing(row: dict, fields: list[str]) -> list[str]:
    return [f for f in fields if not str(row.get(f) or "").strip()]


def evaluate_mandatory_fields(eft_rows: list[dict], rule: dict) -> list[dict]:
    required = rule.get("parameters", {}).get(
        "required_fields",
        ["transaction_id", "value_date", "amount", "currency_code",
         "direction", "originator_name", "beneficiary_name"],
    )
    findings = []
    for row in eft_rows:
        missing = _missing(row, required)
        if missing:
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": str(row.get("transaction_id", "")),
                "severity": rule["severity"],
                "detail": {"missing_fields": missing,
                           "reason": f"Required fields missing: {', '.join(missing)}"},
            })
    return findings


def evaluate_travel_rule(eft_rows: list[dict], rule: dict) -> list[dict]:
    findings = []
    for row in eft_rows:
        missing = _missing(row, TRAVEL_RULE_FIELDS)
        if missing:
            findings.append({
                "rule_code": rule["rule_code"],
                "rule_id": rule.get("rule_id", ""),
                "rule_version": rule.get("version", 1),
                "transaction_id": str(row.get("transaction_id", "")),
                "severity": rule["severity"],
                "detail": {"missing_fields": missing,
                           "reason": f"Travel rule fields missing: {', '.join(missing)}"},
            })
    return findings


# Unified entry point called by the rules registry
def evaluate(eft_rows: list[dict], rep_rows: list[dict], reported_ids: set, rule: dict) -> list[dict]:
    code = rule.get("rule_code", "")
    if code == "FINTRAC_TRAVEL_RULE":
        return evaluate_travel_rule(eft_rows, rule)
    return evaluate_mandatory_fields(eft_rows, rule)
