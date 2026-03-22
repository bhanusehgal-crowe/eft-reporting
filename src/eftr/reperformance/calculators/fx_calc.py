from decimal import Decimal

import pandas as pd

from src.eftr.fx.boc_client import BoCFXClient

TOLERANCE_PCT = Decimal("0.01")  # 1%


def calculate(eft_df: pd.DataFrame) -> list[dict]:
    """
    Recompute cad_amount from BoC rates and compare to recorded cad_amount.
    Returns list of variance/breach dicts.
    """
    if eft_df.empty:
        return []

    client = BoCFXClient()
    results = []

    for _, row in eft_df.iterrows():
        currency = str(row.get("currency_code", "")).upper()
        if currency == "CAD":
            continue

        tx_id = str(row.get("transaction_id", ""))
        try:
            amount = Decimal(str(row.get("amount", 0)))
            recorded_cad = Decimal(str(row.get("cad_amount", 0)))
            value_date = pd.to_datetime(row["value_date"]).date()
        except Exception as e:
            results.append({
                "calculation_type": "FX",
                "transaction_id": tx_id,
                "reported_value": None,
                "reperformed_value": None,
                "variance_absolute": None,
                "variance_pct": None,
                "status": "VARIANCE",
                "detail": {"error": str(e)},
            })
            continue

        try:
            reperformed_cad, rate_used = client.convert_to_cad(amount, currency, value_date)
        except Exception as e:
            results.append({
                "calculation_type": "FX",
                "transaction_id": tx_id,
                "reported_value": recorded_cad,
                "reperformed_value": None,
                "variance_absolute": None,
                "variance_pct": None,
                "status": "VARIANCE",
                "detail": {"error": f"BoC rate fetch failed: {e}"},
            })
            continue

        if recorded_cad == 0:
            continue

        variance_abs = abs(reperformed_cad - recorded_cad)
        variance_pct = variance_abs / recorded_cad

        if variance_pct > TOLERANCE_PCT:
            status = "BREACH"
        elif variance_abs > Decimal("0"):
            status = "VARIANCE"
        else:
            status = "PASS"

        if status != "PASS":
            results.append({
                "calculation_type": "FX",
                "transaction_id": tx_id,
                "reported_value": recorded_cad,
                "reperformed_value": reperformed_cad,
                "variance_absolute": variance_abs,
                "variance_pct": variance_pct,
                "status": status,
                "detail": {
                    "currency": currency,
                    "amount": str(amount),
                    "rate_used": str(rate_used),
                    "recorded_cad": str(recorded_cad),
                    "reperformed_cad": str(reperformed_cad),
                },
            })

    return results
