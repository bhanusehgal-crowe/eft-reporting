import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_session
from src.eftr.models.rule import Rule
from src.eftr.utils.datetime_utils import utcnow

router = APIRouter()


class CreateRuleRequest(BaseModel):
    rule_code: str
    rule_name: str
    description: str
    rule_type: str
    parameters: dict = {}
    severity: str
    effective_from: date
    change_reason: str


class VersionRuleRequest(BaseModel):
    parameters: Optional[dict] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    change_reason: str


def _get_operator(x_operator_id: Optional[str] = Header(None)) -> str:
    if not x_operator_id:
        raise HTTPException(status_code=400, detail="X-Operator-ID header is required")
    return x_operator_id


@router.get("")
def list_rules(session: Session = Depends(get_session)):
    rules = session.query(Rule).filter_by(is_active=True).order_by(Rule.rule_code).all()
    return [
        {
            "rule_id": r.rule_id,
            "rule_code": r.rule_code,
            "version": r.version,
            "rule_name": r.rule_name,
            "severity": r.severity,
            "rule_type": r.rule_type,
            "effective_from": r.effective_from,
            "effective_to": r.effective_to,
            "is_active": r.is_active,
        }
        for r in rules
    ]


@router.post("", status_code=201)
def create_rule(
    request: CreateRuleRequest,
    operator_id: str = Depends(_get_operator),
    session: Session = Depends(get_session),
):
    rule = Rule(
        rule_id=str(uuid.uuid4()),
        rule_code=request.rule_code,
        version=1,
        parent_version_id=None,
        rule_name=request.rule_name,
        description=request.description,
        rule_type=request.rule_type,
        parameters=request.parameters,
        severity=request.severity,
        effective_from=request.effective_from,
        effective_to=None,
        is_active=True,
        change_reason=request.change_reason,
        changed_by=operator_id,
        created_at=utcnow(),
    )
    session.add(rule)
    session.commit()
    return {"rule_id": rule.rule_id, "rule_code": rule.rule_code, "version": rule.version}


@router.put("/{rule_id}/version")
def version_rule(
    rule_id: str,
    request: VersionRuleRequest,
    operator_id: str = Depends(_get_operator),
    session: Session = Depends(get_session),
):
    """Create a new version of a rule (immutable versioning — never updates in place)."""
    existing = session.get(Rule, rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Close existing version
    existing.effective_to = date.today()
    existing.is_active = False

    new_rule = Rule(
        rule_id=str(uuid.uuid4()),
        rule_code=existing.rule_code,
        version=existing.version + 1,
        parent_version_id=rule_id,
        rule_name=existing.rule_name,
        description=request.description or existing.description,
        rule_type=existing.rule_type,
        parameters=request.parameters or existing.parameters,
        severity=request.severity or existing.severity,
        effective_from=date.today(),
        effective_to=None,
        is_active=True,
        change_reason=request.change_reason,
        changed_by=operator_id,
        created_at=utcnow(),
    )
    session.add(new_rule)
    session.commit()
    return {"rule_id": new_rule.rule_id, "rule_code": new_rule.rule_code, "version": new_rule.version}
