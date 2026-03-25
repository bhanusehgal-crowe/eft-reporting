"""
Pre-submission validator for FINTRAC EFT reports.
Runs before XML generation to ensure all mandatory fields are present
and regulatory thresholds are met.
"""

THRESHOLD_CAD = 10_000.00

# (field_key, human_label, category)
_MANDATORY: list[tuple[str, str, str]] = [
    ("reporting_entity_number", "Reporting Entity Number",     "Reporting Entity"),
    ("reporting_entity_name",   "Reporting Entity Name",       "Reporting Entity"),
    ("contact_name",            "Compliance Officer Name",      "Reporting Entity"),
    ("contact_phone",           "Contact Phone",               "Reporting Entity"),
    ("contact_email",           "Contact Email",               "Reporting Entity"),
    ("transaction_date",        "Transaction Date",            "Transaction"),
    ("direction",               "Direction (INITIATION/RECEIPT)", "Transaction"),
    ("amount",                  "Transaction Amount",          "Transaction"),
    ("currency_code",           "Currency Code",               "Transaction"),
    ("cad_amount",              "CAD Equivalent Amount",       "Transaction"),
    ("originator_name",         "Originator Name",             "Parties"),
    ("originator_address",      "Originator Address",          "Parties"),
    ("originator_account",      "Originator Account Number",   "Parties"),
    ("beneficiary_name",        "Beneficiary Name",            "Parties"),
    ("beneficiary_address",     "Beneficiary Address",         "Parties"),
    ("beneficiary_account",     "Beneficiary Account Number",  "Parties"),
]


def _is_missing(val: object) -> bool:
    """Return True if the value is absent or still a [REQUIRED: ...] placeholder."""
    if val is None:
        return True
    s = str(val).strip()
    return not s or s.startswith("[REQUIRED")


def validate_report(report_data: dict) -> dict:
    """
    Run all pre-submission checks.

    Returns:
        {
            "passed": bool,
            "checks": [{"id", "label", "passed", "category"}, ...],
            "errors": ["human-readable error message", ...],
        }
    """
    checks: list[dict] = []
    errors: list[str] = []

    # 1. Mandatory field presence
    for field, label, category in _MANDATORY:
        val = report_data.get(field)
        ok = not _is_missing(val)
        checks.append({
            "id": f"field_{field}",
            "label": f"{label} present",
            "passed": ok,
            "category": category,
        })
        if not ok:
            errors.append(f"Missing or incomplete: {label}")

    # 2. CAD threshold
    try:
        cad = float(report_data.get("cad_amount") or 0)
        ok = cad >= THRESHOLD_CAD
        checks.append({
            "id": "threshold",
            "label": f"CAD equivalent ≥ $10,000 (actual: ${cad:,.2f})",
            "passed": ok,
            "category": "Regulatory Threshold",
        })
        if not ok:
            errors.append(
                f"CAD amount ${cad:,.2f} is below the $10,000 EFTR threshold"
            )
    except (ValueError, TypeError):
        checks.append({
            "id": "threshold",
            "label": "CAD equivalent ≥ $10,000 (could not parse amount)",
            "passed": False,
            "category": "Regulatory Threshold",
        })
        errors.append("Could not parse CAD amount")

    # 3. Direction format
    direction = str(report_data.get("direction") or "").strip().upper()
    ok = direction in ("INITIATION", "RECEIPT")
    checks.append({
        "id": "direction_format",
        "label": f"Direction is INITIATION or RECEIPT (actual: '{direction or 'none'}')",
        "passed": ok,
        "category": "Transaction",
    })
    if not ok:
        errors.append(f"Invalid direction value: '{direction}'")

    # 4. ISO-4217 currency code (3 uppercase letters)
    currency = str(report_data.get("currency_code") or "").strip()
    ok = len(currency) == 3 and currency.isalpha()
    checks.append({
        "id": "currency_format",
        "label": f"Currency is 3-letter ISO-4217 code (actual: '{currency or 'none'}')",
        "passed": ok,
        "category": "Transaction",
    })
    if not ok:
        errors.append(f"Invalid currency code: '{currency}'")

    # 5. Transaction date format (YYYY-MM-DD)
    txn_date = str(report_data.get("transaction_date") or report_data.get("value_date") or "")
    try:
        from datetime import date
        date.fromisoformat(txn_date)
        ok = True
    except (ValueError, TypeError):
        ok = False
    checks.append({
        "id": "date_format",
        "label": f"Transaction date is valid (actual: '{txn_date or 'none'}')",
        "passed": ok,
        "category": "Transaction",
    })
    if not ok:
        errors.append(f"Invalid transaction date: '{txn_date}'")

    return {
        "passed": len(errors) == 0,
        "checks": checks,
        "errors": errors,
    }
