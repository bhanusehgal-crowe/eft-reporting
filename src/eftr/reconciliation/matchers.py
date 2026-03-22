from decimal import Decimal

import pandas as pd


def exact_id_match(
    eft_df: pd.DataFrame, reported_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Tier 1: Exact match on transaction_id ↔ reported_transaction_id.
    Returns (matched, unmatched_eft, unmatched_reported).
    """
    merged = eft_df.merge(
        reported_df,
        left_on="transaction_id",
        right_on="reported_transaction_id",
        how="inner",
        suffixes=("_eft", "_rep"),
    )
    matched_eft_ids = set(merged["transaction_id"])
    matched_rep_ids = set(merged["reported_transaction_id"])

    unmatched_eft = eft_df[~eft_df["transaction_id"].isin(matched_eft_ids)].copy()
    unmatched_rep = reported_df[
        ~reported_df["reported_transaction_id"].isin(matched_rep_ids)
    ].copy()

    return merged, unmatched_eft, unmatched_rep


def fuzzy_match(
    unmatched_eft: pd.DataFrame,
    unmatched_rep: pd.DataFrame,
    amount_tolerance: Decimal = Decimal("0.01"),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Tier 2: Fuzzy match on (cad_amount ± tolerance, value_date, beneficiary_account).
    Returns (matched, remaining_eft, remaining_rep).
    """
    if unmatched_eft.empty or unmatched_rep.empty:
        return pd.DataFrame(), unmatched_eft, unmatched_rep

    matched_rows = []
    used_rep_indices = set()
    remaining_eft_indices = []

    for eft_idx, eft_row in unmatched_eft.iterrows():
        found = False
        eft_amount = float(eft_row.get("cad_amount", 0))
        eft_date = str(eft_row.get("value_date", ""))
        eft_bene_account = str(eft_row.get("beneficiary_account", ""))

        for rep_idx, rep_row in unmatched_rep.iterrows():
            if rep_idx in used_rep_indices:
                continue

            rep_amount = float(rep_row.get("reported_cad_amount") or rep_row.get("reported_amount", 0))
            rep_date = str(rep_row.get("report_date", ""))

            amount_match = abs(eft_amount - rep_amount) <= float(amount_tolerance)
            date_match = eft_date == rep_date
            account_match = (
                eft_bene_account
                and eft_bene_account != ""
                and eft_bene_account == str(rep_row.get("reported_transaction_id", ""))
            )

            if amount_match and date_match:
                matched_rows.append(
                    {**eft_row.to_dict(), **{f"{k}_rep": v for k, v in rep_row.to_dict().items()}}
                )
                used_rep_indices.add(rep_idx)
                found = True
                break

        if not found:
            remaining_eft_indices.append(eft_idx)

    matched_df = pd.DataFrame(matched_rows)
    remaining_eft = unmatched_eft.loc[remaining_eft_indices].copy() if remaining_eft_indices else pd.DataFrame(columns=unmatched_eft.columns)
    remaining_rep = unmatched_rep[~unmatched_rep.index.isin(used_rep_indices)].copy()

    return matched_df, remaining_eft, remaining_rep
