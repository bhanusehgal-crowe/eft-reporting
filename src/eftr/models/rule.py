import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class Rule(Base):
    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    rule_code: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rule_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(
        Enum(
            "THRESHOLD",
            "AGGREGATION",
            "DEADLINE",
            "COMPLETENESS",
            "PATTERN",
            name="rule_type",
        )
    )
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(
        Enum("INFO", "WARN", "BREACH", name="rule_severity"), index=True
    )
    effective_from: Mapped[date] = mapped_column()
    effective_to: Mapped[date | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    change_reason: Mapped[str] = mapped_column(Text, default="")
    changed_by: Mapped[str] = mapped_column(String(255), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )


class RuleFinding(Base):
    __tablename__ = "rule_findings"

    finding_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.run_id"))
    rule_id: Mapped[str] = mapped_column(String(36))
    rule_code: Mapped[str] = mapped_column(String(100), index=True)
    rule_version: Mapped[int] = mapped_column(Integer)
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(
        Enum("INFO", "WARN", "BREACH", name="finding_severity"), index=True
    )
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )
