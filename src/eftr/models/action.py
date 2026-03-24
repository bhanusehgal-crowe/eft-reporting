import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from src.eftr.utils.datetime_utils import utcnow


class ComplianceAction(Base):
    """
    Human-in-the-loop compliance action attached to a rule finding.
    One action per finding (upsert pattern). Tracks status, notes,
    FINTRAC filing reference, and travel-rule decision.
    """

    __tablename__ = "compliance_actions"
    __table_args__ = (UniqueConstraint("finding_id", name="uq_compliance_action_finding"),)

    action_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    finding_id: Mapped[str] = mapped_column(String(36), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)

    # open | under_review | filed | resolved | disputed | escalated
    status: Mapped[str] = mapped_column(String(20), default="open")

    operator_id: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # BREACH findings: FINTRAC filing reference number
    filed_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # WARN travel-rule findings: allow | suspend | reject
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 5-business-day EFTR deadline (BREACH findings only), computed on first upsert
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
