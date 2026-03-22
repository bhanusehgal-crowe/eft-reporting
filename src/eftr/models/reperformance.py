import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class ReperformanceResult(Base):
    __tablename__ = "reperformance_results"

    result_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.run_id"))
    calculation_type: Mapped[str] = mapped_column(String(100), index=True)
    period: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reported_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    reperformed_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    variance_absolute: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    variance_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("PASS", "VARIANCE", "BREACH", name="reperformance_status"), index=True
    )
    threshold_rule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )
