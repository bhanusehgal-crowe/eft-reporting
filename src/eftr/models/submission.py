"""
EFTRSubmission and SubmissionEvent models.

State machine:
  DRAFT → PENDING_APPROVAL → APPROVED → SUBMITTED → ACKNOWLEDGED
       ↘ CHECKER_REJECTED (back to DRAFT)
                                       ↘ FINTRAC_REJECTED → (amend → new DRAFT)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from src.eftr.utils.datetime_utils import utcnow

# Valid status values
STATUSES = [
    "DRAFT",
    "VALIDATED",
    "FILE_READY",
    "PENDING_APPROVAL",
    "CHECKER_REJECTED",
    "APPROVED",
    "SUBMITTED",
    "ACKNOWLEDGED",
    "FINTRAC_REJECTED",
]


class EFTRSubmission(Base):
    """
    Tracks one end-to-end EFTR filing for a single rule finding.
    Supports the full maker-checker workflow through to F2R portal upload
    and acknowledgement ingestion.
    """

    __tablename__ = "eftr_submissions"

    submission_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    finding_id: Mapped[str] = mapped_column(String(36), index=True)
    action_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Workflow state ─────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)

    # ── Dual-control ──────────────────────────────────────────────
    maker_id: Mapped[str] = mapped_column(String(200), default="")
    checker_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Form data (pre-filled from EFT transaction, editable) ─────
    report_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Pre-submission validation ──────────────────────────────────
    validation_passed: Mapped[bool | None] = mapped_column(nullable=True)
    validation_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Generated XML ─────────────────────────────────────────────
    report_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_filename: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Internal approval ─────────────────────────────────────────
    maker_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    checker_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    checker_rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── F2R portal submission ─────────────────────────────────────
    portal_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── F2R acknowledgement ───────────────────────────────────────
    ack_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ack_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── F2R rejection ─────────────────────────────────────────────
    fintrac_rejection_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fintrac_rejection_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Amendment lineage ─────────────────────────────────────────
    amendment_of_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    amendment_number: Mapped[int] = mapped_column(default=1)
    amendment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SubmissionEvent(Base):
    """
    Immutable audit trail for every state transition in an EFTRSubmission.
    """

    __tablename__ = "submission_events"

    event_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    submission_id: Mapped[str] = mapped_column(String(36), index=True)
    operator_id: Mapped[str] = mapped_column(String(200), default="")
    event_type: Mapped[str] = mapped_column(String(50))
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
