"""Seed canonical FINTRAC rules into the database."""
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

import yaml

# Only manipulate sys.path when run as a script, not when imported as a module
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import SessionLocal, engine
from config.settings import settings
from src.eftr.models.rule import Rule

# Ensure tables exist
from config.database import Base
Base.metadata.create_all(engine)


def seed_rules(rules_file: str | None = None, operator: str = "system") -> int:
    if rules_file is None:
        rules_file = Path(__file__).parent.parent / "tests" / "fixtures" / "seed_rules.yaml"

    with open(rules_file) as f:
        data = yaml.safe_load(f)

    rules_config = data.get("rules", [])
    today = date.today()

    with SessionLocal() as session:
        seeded = 0
        for rc in rules_config:
            # Check if rule already exists
            from sqlalchemy import select
            existing = session.execute(
                select(Rule).where(
                    Rule.rule_code == rc["rule_code"],
                    Rule.is_active == True,
                )
            ).first()
            if existing:
                print(f"  Rule {rc['rule_code']} already exists, skipping.")
                continue

            rule = Rule(
                rule_id=str(uuid.uuid4()),
                rule_code=rc["rule_code"],
                version=1,
                parent_version_id=None,
                rule_name=rc["rule_name"],
                description=rc["description"],
                rule_type=rc["rule_type"],
                parameters=rc.get("parameters", {}),
                severity=rc["severity"],
                effective_from=today,
                effective_to=None,
                is_active=True,
                change_reason="Initial seed",
                changed_by=operator,
                created_at=datetime.utcnow(),
            )
            session.add(rule)
            seeded += 1
            print(f"  Seeded rule: {rc['rule_code']} [{rc['severity']}]")

        session.commit()
        print(f"\nSeeded {seeded} rules.")
        return seeded


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed FINTRAC rules into the database")
    parser.add_argument("--file", default=None, help="Path to rules YAML file")
    parser.add_argument("--operator", default="system", help="Operator ID")
    args = parser.parse_args()

    print("Seeding FINTRAC rules...")
    seed_rules(args.file, args.operator)
