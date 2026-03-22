import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class ReportedTransaction(Base):
    __tablename__ = "reported_transactions"

    reported_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.run_id"))
    source_file: Mapped[str] = mapped_column(String(500))
    row_hash: Mapped[str] = mapped_column(String(64), index=True)
    report_reference: Mapped[str] = mapped_column(String(255))
    reporting_entity_id: Mapped[str] = mapped_column(String(255))
    reported_transaction_id: Mapped[str] = mapped_column(String(255), index=True)
    report_date: Mapped[date] = mapped_column()
    reported_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    reported_currency: Mapped[str] = mapped_column(String(3))
    reported_cad_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    report_type: Mapped[str] = mapped_column(String(100))
    direction: Mapped[str] = mapped_column(
        Enum("INITIATION", "RECEIPT", name="reported_direction")
    )
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )
