import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    run_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", name="run_status"),
        default="PENDING",
    )
    triggered_by: Mapped[str] = mapped_column(String(255))
    operator_id: Mapped[str] = mapped_column(String(255))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    result_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.run_id"))
    eft_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    reported_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        Enum("MATCHED", "MISSED", "PHANTOM", name="reconciliation_status"), index=True
    )
    match_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    variance_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )
