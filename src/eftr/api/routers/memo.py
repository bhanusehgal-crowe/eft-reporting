"""
Manager Memo generator.
Reads live DB state and produces a structured JSON compliance summary
suitable for officer review and management reporting.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config.database import get_session
from src.eftr.models.action import ComplianceAction
from src.eftr.models.reconciliation import ReconciliationResult, ReconciliationRun
from src.eftr.models.rule import RuleFinding
from src.eftr.utils.business_days import add_business_days, business_days_between

router = APIRouter()

_DEADLINE_RULES = {
    "FINTRAC_SINGLE_THRESHOLD",
    "FINTRAC_24HR_AGGREGATION",
    "FINTRAC_FILING_DEADLINE",
}
_TRAVEL_RULES = {"FINTRAC_TRAVEL_RULE", "FINTRAC_MANDATORY_FIELDS"}

_ACTION_DESCRIPTIONS = {
    "FINTRAC_SINGLE_THRESHOLD": "File EFTR for unreported transaction ≥ CAD $10,000",
    "FINTRAC_24HR_AGGREGATION": "File EFTR for aggregated transactions exceeding CAD $10,000 within 24-hour window",
    "FINTRAC_FILING_DEADLINE": "File corrected EFTR — original filing exceeded 5-business-day deadline",
    "FINTRAC_MANDATORY_FIELDS": "Obtain missing mandatory fields and submit corrected EFTR",
    "FINTRAC_TRAVEL_RULE": "Document exception decision (Allow / Suspend / Reject) for missing originator/beneficiary info",
    "FINTRAC_FX_CONVERSION": "Verify CAD conversion using Bank of Canada Valet API rates",
    "FINTRAC_OVER_REPORTING": "Review over-reported transaction; consider voluntary correction",
}


def _get_deadline(finding: RuleFinding, action: ComplianceAction | None) -> date | None:
    if action and action.deadline:
        return action.deadline
    if finding.rule_code not in _DEADLINE_RULES:
        return None
    detail = finding.detail or {}
    vd_str = detail.get("value_date") or detail.get("transaction_date")
    if not vd_str:
        return None
    try:
        return add_business_days(date.fromisoformat(str(vd_str)), 5)
    except (ValueError, TypeError):
        return None


def _days_remaining(deadline: date) -> int:
    today = date.today()
    if deadline < today:
        return -business_days_between(deadline, today)
    return business_days_between(today, deadline)


def generate_memo(run_id: str, session: Session) -> dict:
    run = session.get(ReconciliationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    recon = session.query(ReconciliationResult).filter_by(run_id=run_id).all()
    findings = session.query(RuleFinding).filter_by(run_id=run_id).all()
    all_actions = session.query(ComplianceAction).filter_by(run_id=run_id).all()
    action_map = {a.finding_id: a for a in all_actions}

    matched  = sum(1 for r in recon if r.status == "MATCHED")
    missed   = sum(1 for r in recon if r.status == "MISSED")
    phantom  = sum(1 for r in recon if r.status == "PHANTOM")
    breaches = [f for f in findings if f.severity == "BREACH"]
    warnings = [f for f in findings if f.severity == "WARN"]

    # ── Breach summary by rule ────────────────────────────────────
    rule_counts: dict[str, int] = {}
    for f in breaches:
        rule_counts[f.rule_code] = rule_counts.get(f.rule_code, 0) + 1

    breach_summary = []
    for rule_code, count in sorted(rule_counts.items()):
        entry: dict = {
            "rule": rule_code.replace("FINTRAC_", ""),
            "count": count,
            "action_required": _ACTION_DESCRIPTIONS.get(rule_code, "Review required"),
        }
        if rule_code in _DEADLINE_RULES:
            rule_findings = [f for f in breaches if f.rule_code == rule_code]
            deadlines = [
                dl for f in rule_findings
                if (dl := _get_deadline(f, action_map.get(f.finding_id))) is not None
            ]
            if deadlines:
                earliest = min(deadlines)
                entry["earliest_deadline"] = earliest.isoformat()
                entry["days_remaining"] = _days_remaining(earliest)
        breach_summary.append(entry)

    # ── Overdue / urgent filings ──────────────────────────────────
    overdue = []
    for f in breaches:
        if f.rule_code not in _DEADLINE_RULES:
            continue
        a = action_map.get(f.finding_id)
        if a and a.status in ("filed", "resolved"):
            continue
        dl = _get_deadline(f, a)
        if dl is None:
            continue
        dr = _days_remaining(dl)
        if dr <= 2:
            overdue.append({
                "transaction_id": f.transaction_id,
                "rule": f.rule_code.replace("FINTRAC_", ""),
                "deadline": dl.isoformat(),
                "days_remaining": dr,
                "status": "OVERDUE" if dr < 0 else "URGENT",
            })

    # ── Travel rule exceptions ────────────────────────────────────
    travel_exceptions = []
    for f in warnings:
        if f.rule_code not in _TRAVEL_RULES:
            continue
        a = action_map.get(f.finding_id)
        if a and a.decision:
            continue  # already logged
        detail = f.detail or {}
        travel_exceptions.append({
            "transaction_id": f.transaction_id,
            "rule": f.rule_code.replace("FINTRAC_", ""),
            "missing_fields": detail.get("missing_fields", []),
            "current_status": a.status if a else "open",
        })

    # ── Recommended actions ───────────────────────────────────────
    recommended: list[str] = []

    unfiled_breach_count = sum(
        1 for f in breaches
        if f.rule_code in _DEADLINE_RULES
        and (not (a := action_map.get(f.finding_id)) or a.status not in ("filed", "resolved"))
    )
    if unfiled_breach_count:
        earliest_dl: date | None = None
        for f in [f for f in breaches if f.rule_code in _DEADLINE_RULES]:
            dl = _get_deadline(f, action_map.get(f.finding_id))
            if dl and (earliest_dl is None or dl < earliest_dl):
                earliest_dl = dl
        dl_str = f" — earliest deadline {earliest_dl.isoformat()}" if earliest_dl else ""
        recommended.append(
            f"File {unfiled_breach_count} outstanding EFTR"
            f"{'s' if unfiled_breach_count > 1 else ''}{dl_str}"
        )

    if overdue:
        recommended.append(
            f"URGENT: {len(overdue)} filing"
            f"{'s are' if len(overdue) > 1 else ' is'} overdue or within 2 business days"
            " — escalate immediately to senior compliance officer"
        )

    if travel_exceptions:
        recommended.append(
            f"Document exception decisions (Allow / Suspend / Reject) for "
            f"{len(travel_exceptions)} transaction"
            f"{'s' if len(travel_exceptions) > 1 else ''} missing Travel Rule information"
        )

    fx_count = sum(1 for f in warnings if f.rule_code == "FINTRAC_FX_CONVERSION")
    if fx_count:
        recommended.append(
            f"Verify CAD conversion rates for {fx_count} transaction"
            f"{'s' if fx_count > 1 else ''} using Bank of Canada Valet API"
        )

    over_count = sum(1 for f in findings if f.severity == "INFO")
    if over_count:
        recommended.append(
            f"Review {over_count} over-reported transaction"
            f"{'s' if over_count > 1 else ''} — consider voluntary correction to FINTRAC"
        )

    if not recommended:
        recommended.append("No immediate action required — all findings have been addressed")

    # ── Executive summary ─────────────────────────────────────────
    total_tx = len(recon)
    exec_summary = (
        f"Analysis of {total_tx} EFT transaction{'s' if total_tx != 1 else ''} "
        f"identified {len(breaches)} regulatory breach{'es' if len(breaches) != 1 else ''} "
        f"and {len(warnings)} warning{'s' if len(warnings) != 1 else ''} requiring compliance action. "
        f"{matched} transaction{'s' if matched != 1 else ''} matched filed EFTRs; "
        f"{missed} transaction{'s' if missed != 1 else ''} had no corresponding EFTR on file."
    )

    actions_taken = sum(1 for a in all_actions if a.status != "open")

    return {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "operator_id": run.operator_id,
        "period": (
            f"EFT data analysed on "
            f"{run.completed_at.date().isoformat() if run.completed_at else date.today().isoformat()}"
        ),
        "executive_summary": exec_summary,
        "kpi": {
            "total_transactions": total_tx,
            "matched": matched,
            "missed": missed,
            "phantom": phantom,
            "breaches": len(breaches),
            "warnings": len(warnings),
            "actions_taken": actions_taken,
        },
        "breach_summary": breach_summary,
        "overdue_filings": overdue,
        "travel_rule_exceptions": travel_exceptions,
        "recommended_actions": recommended,
        "disclaimer": (
            "This memo is generated by the EFTR Regulatory Assurance Platform and reflects "
            "system-detected findings only. Review and sign-off by a qualified compliance officer "
            "is required before any submission to FINTRAC. "
            "This document does not constitute legal advice."
        ),
    }


@router.get("/{run_id}")
def get_memo(run_id: str, session: Session = Depends(get_session)):
    """Return the live compliance memo for a run (re-generated on each call)."""
    return generate_memo(run_id, session)
