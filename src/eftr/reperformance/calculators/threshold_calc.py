from decimal import Decimal

import pandas as pd

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


def calculate(eft_df: pd.DataFrame, rep_df: pd.DataFrame) -> list[dict]:
    """
    Recompute which EFTs exceed $10,000 CAD using cad_amount on record.
    Compare to what was reported.
    """
    if eft_df.empty:
        return []

    reported_ids = set()
    if not rep_df.empty and "reported_transaction_id" in rep_df.columns:
        reported_ids = set(rep_df["reported_transaction_id"].astype(str))

    results = []
    for _, row in eft_df.iterrows():
        tx_id = str(row.get("transaction_id", ""))
        try:
            cad_amount = Decimal(str(row.get("cad_amount", 0)))
        except Exception:
            cad_amount = Decimal("0")

        should_be_reported = cad_amount >= FINTRAC_THRESHOLD_CAD
        was_reported = tx_id in reported_ids

        if should_be_reported != was_reported:
            status = "BREACH" if should_be_reported and not was_reported else "VARIANCE"
            results.append({
                "calculation_type": "THRESHOLD",
                "transaction_id": tx_id,
                "reported_value": Decimal("1") if was_reported else Decimal("0"),
                "reperformed_value": Decimal("1") if should_be_reported else Decimal("0"),
                "variance_absolute": Decimal("1"),
                "variance_pct": None,
                "status": status,
                "detail": {
                    "cad_amount": str(cad_amount),
                    "threshold_cad": str(FINTRAC_THRESHOLD_CAD),
                    "should_be_reported": should_be_reported,
                    "was_reported": was_reported,
                },
            })

    return results
