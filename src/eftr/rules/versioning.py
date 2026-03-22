"""
Rule versioning: immutable version history for FINTRAC rules.
Never UPDATE a rule row; instead close the current version and insert a new one.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.eftr.models.rule import Rule
from src.eftr.utils.datetime_utils import utcnow


def create_new_version(
    session: Session,
    rule_id: str,
    change_reason: str,
    changed_by: str,
    parameters: Optional[dict] = None,
    description: Optional[str] = None,
    severity: Optional[str] = None,
) -> Rule:
    """
    Creates a new version of a rule by:
    1. Setting effective_to = today and is_active = False on the current version.
    2. Inserting a new row with version + 1.

    Returns the newly created rule.
    """
    existing = session.get(Rule, rule_id)
    if not existing:
        raise ValueError(f"Rule {rule_id} not found")
    if not existing.is_active:
        raise ValueError(f"Rule {rule_id} is already inactive")

    today = date.today()
    existing.effective_to = today
    existing.is_active = False

    new_rule = Rule(
        rule_id=str(uuid.uuid4()),
        rule_code=existing.rule_code,
        version=existing.version + 1,
        parent_version_id=rule_id,
        rule_name=existing.rule_name,
        description=description or existing.description,
        rule_type=existing.rule_type,
        parameters=parameters if parameters is not None else existing.parameters,
        severity=severity or existing.severity,
        effective_from=today,
        effective_to=None,
        is_active=True,
        change_reason=change_reason,
        changed_by=changed_by,
        created_at=utcnow(),
    )
    session.add(new_rule)
    session.flush()
    return new_rule
