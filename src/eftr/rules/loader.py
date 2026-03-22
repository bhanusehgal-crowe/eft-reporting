from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.eftr.models.rule import Rule


def load_active_rules(session: Session, as_of: date | None = None) -> list[dict]:
    """Return all currently active rules as dicts."""
    as_of = as_of or date.today()
    stmt = (
        select(Rule)
        .where(
            Rule.is_active == True,
            Rule.effective_from <= as_of,
        )
        .order_by(Rule.rule_code, Rule.version.desc())
    )
    rules = session.execute(stmt).scalars().all()

    # Return only the highest version per rule_code
    seen = set()
    result = []
    for rule in rules:
        if rule.rule_code not in seen:
            seen.add(rule.rule_code)
            result.append(
                {
                    "rule_id": rule.rule_id,
                    "rule_code": rule.rule_code,
                    "version": rule.version,
                    "rule_name": rule.rule_name,
                    "description": rule.description,
                    "rule_type": rule.rule_type,
                    "parameters": rule.parameters,
                    "severity": rule.severity,
                }
            )
    return result
