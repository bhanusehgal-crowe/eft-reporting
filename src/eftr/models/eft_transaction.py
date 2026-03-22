import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class EFTTransaction(Base):
    __tablename__ = "eft_transactions"

    transaction_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.run_id"))
    source_file: Mapped[str] = mapped_column(String(500))
    row_hash: Mapped[str] = mapped_column(String(64), index=True)
    value_date: Mapped[date] = mapped_column()
    settlement_date: Mapped[date | None] = mapped_column(nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency_code: Mapped[str] = mapped_column(String(3))
    cad_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    cad_conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    direction: Mapped[str] = mapped_column(
        Enum("INITIATION", "RECEIPT", name="eft_direction"), index=True
    )
    originator_name: Mapped[str] = mapped_column(Text)
    originator_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    originator_account: Mapped[str | None] = mapped_column(String(255), nullable=True)
    beneficiary_name: Mapped[str] = mapped_column(Text)
    beneficiary_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    beneficiary_account: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow()
    )
