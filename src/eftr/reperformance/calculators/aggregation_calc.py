from decimal import Decimal

import pandas as pd

FINTRAC_THRESHOLD_CAD = Decimal("10000.00")


def calculate(eft_df: pd.DataFrame, rep_df: pd.DataFrame) -> list[dict]:
    """
    Recompute 24-hour window groupings and compare to what was reported.
    """
    if eft_df.empty:
        return []

    eft_df = eft_df.copy()
    eft_df["value_date"] = pd.to_datetime(eft_df["value_date"]).dt.date
    eft_df["cad_amount"] = pd.to_numeric(eft_df["cad_amount"], errors="coerce").fillna(0)

    def get_party_id(row):
        if str(row.get("direction", "")) == "RECEIPT":
            return str(row.get("beneficiary_account") or row.get("beneficiary_name", "UNKNOWN"))
        return str(row.get("originator_account") or row.get("originator_name", "UNKNOWN"))

    eft_df["party_id"] = eft_df.apply(get_party_id, axis=1)

    reported_ids = set()
    if not rep_df.empty and "reported_transaction_id" in rep_df.columns:
        reported_ids = set(rep_df["reported_transaction_id"].astype(str))

    results = []
    groups = eft_df.groupby(["party_id", "direction", "value_date"])
    for (party_id, direction, value_date), group in groups:
        if len(group) < 2:
            continue

        total_cad = Decimal(str(group["cad_amount"].sum()))
        tx_ids = group["transaction_id"].astype(str).tolist()
        reported_in_group = [t for t in tx_ids if t in reported_ids]

        if total_cad >= FINTRAC_THRESHOLD_CAD and not reported_in_group:
            results.append({
                "calculation_type": "AGGREGATION",
                "transaction_id": ",".join(tx_ids[:5]),
                "reported_value": Decimal("0"),
                "reperformed_value": total_cad,
                "variance_absolute": total_cad,
                "variance_pct": None,
                "status": "BREACH",
                "detail": {
                    "party_id": party_id,
                    "direction": direction,
                    "value_date": str(value_date),
                    "total_cad": str(total_cad),
                    "tx_count": len(tx_ids),
                },
            })

    return results
