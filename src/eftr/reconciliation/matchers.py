"""Reconciliation matchers — pandas-free."""
from decimal import Decimal


def exact_id_match(
    eft_rows: list[dict], reported_rows: list[dict]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Tier 1: match transaction_id ↔ reported_transaction_id exactly."""
    rep_by_tid = {str(r.get("reported_transaction_id", "")): r for r in reported_rows}

    matched, unmatched_eft, matched_rep_ids = [], [], set()
    for eft in eft_rows:
        tid = str(eft.get("transaction_id", ""))
        if tid in rep_by_tid:
            rep = rep_by_tid[tid]
            matched.append({**eft, **{f"{k}_rep": v for k, v in rep.items()}})
            matched_rep_ids.add(tid)
        else:
            unmatched_eft.append(eft)

    unmatched_rep = [r for r in reported_rows
                     if str(r.get("reported_transaction_id", "")) not in matched_rep_ids]
    return matched, unmatched_eft, unmatched_rep


def fuzzy_match(
    unmatched_eft: list[dict],
    unmatched_rep: list[dict],
    amount_tolerance: Decimal = Decimal("0.01"),
) -> tuple[list[dict], list[dict], list[dict]]:
    """Tier 2: fuzzy match on (cad_amount ± tolerance, value_date)."""
    if not unmatched_eft or not unmatched_rep:
        return [], unmatched_eft, unmatched_rep

    matched, used_rep_indices, remaining_eft_indices = [], set(), []

    for eft in unmatched_eft:
        try:
            eft_amount = float(eft.get("cad_amount") or 0)
        except (ValueError, TypeError):
            eft_amount = 0.0
        eft_date = str(eft.get("value_date", ""))[:10]
        found = False

        for i, rep in enumerate(unmatched_rep):
            if i in used_rep_indices:
                continue
            try:
                rep_amount = float(rep.get("reported_cad_amount") or rep.get("reported_amount") or 0)
            except (ValueError, TypeError):
                rep_amount = 0.0
            rep_date = str(rep.get("report_date", ""))[:10]

            if abs(eft_amount - rep_amount) <= float(amount_tolerance) and eft_date == rep_date:
                matched.append({**eft, **{f"{k}_rep": v for k, v in rep.items()}})
                used_rep_indices.add(i)
                found = True
                break

        if not found:
            remaining_eft_indices.append(eft)

    remaining_rep = [r for i, r in enumerate(unmatched_rep) if i not in used_rep_indices]
    return matched, remaining_eft_indices, remaining_rep
