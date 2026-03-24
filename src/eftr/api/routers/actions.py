import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_session
from src.eftr.models.action import ComplianceAction
from src.eftr.models.rule import RuleFinding
from src.eftr.utils.business_days import add_business_days
from src.eftr.utils.datetime_utils import utcnow

router = APIRouter()

# Rules that carry a 5-business-day EFTR filing deadline
_DEADLINE_RULES = {
    "FINTRAC_SINGLE_THRESHOLD",
    "FINTRAC_24HR_AGGREGATION",
    "FINTRAC_FILING_DEADLINE",
}


def _compute_deadline(finding: RuleFinding) -> Optional[date]:
    """Derive the 5-biz-day filing deadline from the finding's detail JSON."""
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


def _serialize(a: ComplianceAction) -> dict:
    return {
        "action_id": a.action_id,
        "finding_id": a.finding_id,
        "run_id": a.run_id,
        "status": a.status,
        "operator_id": a.operator_id,
        "notes": a.notes,
        "filed_ref": a.filed_ref,
        "decision": a.decision,
        "deadline": a.deadline.isoformat() if a.deadline else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


class UpsertActionRequest(BaseModel):
    finding_id: str
    run_id: str
    operator_id: str
    status: str = "open"
    notes: Optional[str] = None
    filed_ref: Optional[str] = None
    decision: Optional[str] = None


class PatchActionRequest(BaseModel):
    status: Optional[str] = None
    operator_id: Optional[str] = None
    notes: Optional[str] = None
    filed_ref: Optional[str] = None
    decision: Optional[str] = None


@router.post("", status_code=200)
def upsert_action(body: UpsertActionRequest, session: Session = Depends(get_session)):
    """Create or update the compliance action for a finding (one per finding)."""
    existing = session.query(ComplianceAction).filter_by(finding_id=body.finding_id).first()
    finding = session.get(RuleFinding, body.finding_id)
    deadline = _compute_deadline(finding) if finding else None

    if existing:
        if body.status:
            existing.status = body.status
        if body.notes is not None:
            existing.notes = body.notes
        if body.filed_ref is not None:
            existing.filed_ref = body.filed_ref
        if body.decision is not None:
            existing.decision = body.decision
        existing.operator_id = body.operator_id
        if deadline and not existing.deadline:
            existing.deadline = deadline
        existing.updated_at = utcnow()
        session.commit()
        return _serialize(existing)

    action = ComplianceAction(
        action_id=str(uuid.uuid4()),
        finding_id=body.finding_id,
        run_id=body.run_id,
        status=body.status,
        operator_id=body.operator_id,
        notes=body.notes,
        filed_ref=body.filed_ref,
        decision=body.decision,
        deadline=deadline,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(action)
    session.commit()
    return _serialize(action)


@router.get("")
def list_actions(run_id: str, session: Session = Depends(get_session)):
    """List all compliance actions for a run, keyed by finding_id."""
    actions = session.query(ComplianceAction).filter_by(run_id=run_id).all()
    return [_serialize(a) for a in actions]


@router.patch("/{action_id}")
def patch_action(
    action_id: str,
    body: PatchActionRequest,
    session: Session = Depends(get_session),
):
    """Partially update an existing compliance action."""
    action = session.get(ComplianceAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if body.status is not None:
        action.status = body.status
    if body.operator_id is not None:
        action.operator_id = body.operator_id
    if body.notes is not None:
        action.notes = body.notes
    if body.filed_ref is not None:
        action.filed_ref = body.filed_ref
    if body.decision is not None:
        action.decision = body.decision
    action.updated_at = utcnow()
    session.commit()
    return _serialize(action)
