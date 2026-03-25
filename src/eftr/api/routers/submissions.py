"""
/submissions  — End-to-end EFTR filing workflow.

Lifecycle:
  POST /submissions                      → DRAFT (pre-filled from EFT transaction)
  PUT  /submissions/{id}/report-data     → update editable fields
  POST /submissions/{id}/validate        → DRAFT|VALIDATED (runs pre-submission checks)
  POST /submissions/{id}/generate-file   → FILE_READY (generates FINTRAC XML)
  GET  /submissions/{id}/download        → download XML file
  POST /submissions/{id}/submit-for-approval → PENDING_APPROVAL
  POST /submissions/{id}/approve         → APPROVED
  POST /submissions/{id}/reject          → CHECKER_REJECTED
  POST /submissions/{id}/confirm-upload  → SUBMITTED
  POST /submissions/{id}/acknowledge     → ACKNOWLEDGED
  POST /submissions/{id}/record-rejection→ FINTRAC_REJECTED
  POST /submissions/{id}/amend           → new DRAFT linked as amendment
  GET  /submissions                      → list by run_id / finding_id
  GET  /submissions/{id}                 → full detail + events
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_session
from src.eftr.filing.validator import validate_report
from src.eftr.filing.xml_generator import generate_eftr_xml
from src.eftr.models.action import ComplianceAction
from src.eftr.models.eft_transaction import EFTTransaction
from src.eftr.models.rule import RuleFinding
from src.eftr.models.submission import EFTRSubmission, SubmissionEvent
from src.eftr.utils.datetime_utils import utcnow

router = APIRouter()


# ── Serialisation helpers ─────────────────────────────────────────

def _ser_sub(s: EFTRSubmission) -> dict:
    return {
        "submission_id": s.submission_id,
        "finding_id": s.finding_id,
        "action_id": s.action_id,
        "run_id": s.run_id,
        "transaction_id": s.transaction_id,
        "status": s.status,
        "maker_id": s.maker_id,
        "checker_id": s.checker_id,
        "report_data": s.report_data,
        "validation_passed": s.validation_passed,
        "validation_result": s.validation_result,
        "report_filename": s.report_filename,
        "has_xml": bool(s.report_xml),
        "maker_notes": s.maker_notes,
        "checker_notes": s.checker_notes,
        "portal_ref": s.portal_ref,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
        "ack_number": s.ack_number,
        "ack_received_at": s.ack_received_at.isoformat() if s.ack_received_at else None,
        "fintrac_rejection_code": s.fintrac_rejection_code,
        "fintrac_rejection_detail": s.fintrac_rejection_detail,
        "amendment_of_id": s.amendment_of_id,
        "amendment_number": s.amendment_number,
        "amendment_reason": s.amendment_reason,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _ser_event(e: SubmissionEvent) -> dict:
    return {
        "event_id": e.event_id,
        "submission_id": e.submission_id,
        "operator_id": e.operator_id,
        "event_type": e.event_type,
        "from_status": e.from_status,
        "to_status": e.to_status,
        "notes": e.notes,
        "detail": e.detail,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _add_event(
    session: Session,
    submission: EFTRSubmission,
    event_type: str,
    operator_id: str,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    notes: Optional[str] = None,
    detail: Optional[dict] = None,
):
    ev = SubmissionEvent(
        event_id=str(uuid.uuid4()),
        submission_id=submission.submission_id,
        operator_id=operator_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        notes=notes,
        detail=detail,
        created_at=utcnow(),
    )
    session.add(ev)


def _get_or_404(session: Session, submission_id: str) -> EFTRSubmission:
    sub = session.get(EFTRSubmission, submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


# ── Pre-populate report_data from EFT transaction ────────────────

def _build_report_data(
    finding: RuleFinding,
    txn: Optional[EFTTransaction],
    operator_id: str,
) -> dict:
    """Assemble the report_data dict, pre-filling from the EFT transaction where available."""
    detail = finding.detail or {}

    # Transaction fields — prefer full EFT record, fall back to finding.detail
    def _str(v) -> str:
        return "" if v is None else str(v)

    report_data: dict = {
        # Reporting entity — must be filled in by the user
        "reporting_entity_number": "",
        "reporting_entity_name": "",
        "reporting_entity_type": "BANK",
        "contact_name": "",
        "contact_phone": "",
        "contact_email": "",
        # Transaction
        "transaction_id": finding.transaction_id or "",
        "transaction_date": (
            _str(txn.value_date) if txn else _str(detail.get("value_date") or detail.get("transaction_date"))
        ),
        "value_date": (
            _str(txn.value_date) if txn else _str(detail.get("value_date"))
        ),
        "settlement_date": _str(txn.settlement_date) if txn else "",
        "direction": (
            _str(txn.direction) if txn else _str(detail.get("direction"))
        ),
        "amount": (
            str(float(txn.amount)) if txn else _str(detail.get("amount"))
        ),
        "currency_code": (
            _str(txn.currency_code) if txn else "CAD"
        ),
        "cad_amount": (
            str(float(txn.cad_amount)) if txn else _str(detail.get("cad_amount"))
        ),
        "cad_conversion_rate": (
            str(float(txn.cad_conversion_rate)) if txn and txn.cad_conversion_rate else ""
        ),
        "transaction_type": _str(txn.transaction_type) if txn else "EFT",
        # Originator / Conductor
        "originator_name": _str(txn.originator_name) if txn else "",
        "originator_address": _str(txn.originator_address) if txn else "",
        "originator_account": _str(txn.originator_account) if txn else "",
        # Beneficiary
        "beneficiary_name": _str(txn.beneficiary_name) if txn else "",
        "beneficiary_address": _str(txn.beneficiary_address) if txn else "",
        "beneficiary_account": _str(txn.beneficiary_account) if txn else "",
        "beneficiary_institution": "",
        "beneficiary_country": "",
        "counterparty_id": _str(txn.counterparty_id) if txn else "",
        # Filing metadata
        "submitted_by": operator_id,
        "approved_by": "",
        "filing_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "remarks": "",
        # Amendment (blank for original filings)
        "amendment_of_ref": "",
        "amendment_reason": "",
    }
    return report_data


# ── Routes ────────────────────────────────────────────────────────

class CreateSubmissionRequest(BaseModel):
    finding_id: str
    run_id: str
    operator_id: str


@router.post("", status_code=201)
def create_submission(body: CreateSubmissionRequest, session: Session = Depends(get_session)):
    """
    Create a new DRAFT submission for a finding.
    If a non-terminal submission already exists for this finding, return it.
    """
    # Return existing open submission if one exists
    existing = (
        session.query(EFTRSubmission)
        .filter_by(finding_id=body.finding_id)
        .filter(EFTRSubmission.status.notin_(["ACKNOWLEDGED", "FINTRAC_REJECTED"]))
        .order_by(EFTRSubmission.created_at.desc())
        .first()
    )
    if existing:
        return _ser_sub(existing)

    finding = session.get(RuleFinding, body.finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Try to load the EFT transaction for pre-population
    txn: Optional[EFTTransaction] = None
    if finding.transaction_id:
        txn = (
            session.query(EFTTransaction)
            .filter_by(transaction_id=finding.transaction_id, run_id=body.run_id)
            .first()
        )

    # Look up existing compliance action
    action = session.query(ComplianceAction).filter_by(finding_id=body.finding_id).first()

    report_data = _build_report_data(finding, txn, body.operator_id)

    sub = EFTRSubmission(
        submission_id=str(uuid.uuid4()),
        finding_id=body.finding_id,
        action_id=action.action_id if action else None,
        run_id=body.run_id,
        transaction_id=finding.transaction_id,
        status="DRAFT",
        maker_id=body.operator_id,
        report_data=report_data,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(sub)
    _add_event(session, sub, "CREATED", body.operator_id, to_status="DRAFT",
               detail={"finding_id": body.finding_id, "transaction_id": finding.transaction_id})
    session.commit()
    return _ser_sub(sub)


class UpdateReportDataRequest(BaseModel):
    report_data: dict
    operator_id: str


@router.put("/{submission_id}/report-data")
def update_report_data(
    submission_id: str,
    body: UpdateReportDataRequest,
    session: Session = Depends(get_session),
):
    """Overwrite the editable report_data fields (called from wizard Step 1)."""
    sub = _get_or_404(session, submission_id)
    if sub.status not in ("DRAFT", "CHECKER_REJECTED", "VALIDATED"):
        raise HTTPException(status_code=400, detail=f"Cannot edit in status {sub.status}")
    sub.report_data = body.report_data
    # Reset validation if fields changed
    if sub.status == "VALIDATED":
        sub.status = "DRAFT"
        sub.validation_passed = None
        sub.validation_result = None
    sub.updated_at = utcnow()
    _add_event(session, sub, "REPORT_DATA_UPDATED", body.operator_id)
    session.commit()
    return _ser_sub(sub)


class OperatorRequest(BaseModel):
    operator_id: str
    notes: Optional[str] = None


@router.post("/{submission_id}/validate")
def run_validation(
    submission_id: str,
    body: OperatorRequest,
    session: Session = Depends(get_session),
):
    """Run pre-submission validation against the current report_data."""
    sub = _get_or_404(session, submission_id)
    if sub.status not in ("DRAFT", "CHECKER_REJECTED", "VALIDATED"):
        raise HTTPException(status_code=400, detail=f"Cannot validate in status {sub.status}")

    result = validate_report(sub.report_data or {})
    sub.validation_passed = result["passed"]
    sub.validation_result = result
    if result["passed"]:
        sub.status = "VALIDATED"
    sub.updated_at = utcnow()
    _add_event(
        session, sub, "VALIDATED", body.operator_id,
        from_status="DRAFT", to_status=sub.status,
        detail={"passed": result["passed"], "error_count": len(result["errors"])},
    )
    session.commit()
    return {**_ser_sub(sub), "validation_result": result}


@router.post("/{submission_id}/generate-file")
def generate_file(
    submission_id: str,
    body: OperatorRequest,
    session: Session = Depends(get_session),
):
    """Generate the FINTRAC XML file. Requires validation to have passed."""
    sub = _get_or_404(session, submission_id)
    if sub.status not in ("VALIDATED",):
        raise HTTPException(
            status_code=400,
            detail="Pre-submission validation must pass before generating the filing document."
        )

    xml, filename = generate_eftr_xml(sub.report_data or {}, sub.submission_id)
    sub.report_xml = xml
    sub.report_filename = filename
    sub.status = "FILE_READY"
    sub.updated_at = utcnow()
    _add_event(
        session, sub, "FILE_GENERATED", body.operator_id,
        from_status="VALIDATED", to_status="FILE_READY",
        detail={"filename": filename},
    )
    session.commit()
    return _ser_sub(sub)


@router.get("/{submission_id}/download")
def download_xml(submission_id: str, session: Session = Depends(get_session)):
    """Stream the generated XML file for download."""
    sub = _get_or_404(session, submission_id)
    if not sub.report_xml:
        raise HTTPException(status_code=404, detail="XML not yet generated for this submission")
    filename = sub.report_filename or f"EFTR_{sub.submission_id[:8]}.xml"
    return Response(
        content=sub.report_xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class SubmitForApprovalRequest(BaseModel):
    operator_id: str
    maker_notes: Optional[str] = None


@router.post("/{submission_id}/submit-for-approval")
def submit_for_approval(
    submission_id: str,
    body: SubmitForApprovalRequest,
    session: Session = Depends(get_session),
):
    """Maker submits the generated file for checker review."""
    sub = _get_or_404(session, submission_id)
    if sub.status != "FILE_READY":
        raise HTTPException(status_code=400, detail=f"File must be generated first (current: {sub.status})")
    prev = sub.status
    sub.status = "PENDING_APPROVAL"
    sub.maker_notes = body.maker_notes
    sub.updated_at = utcnow()
    _add_event(
        session, sub, "SUBMITTED_FOR_APPROVAL", body.operator_id,
        from_status=prev, to_status="PENDING_APPROVAL",
        notes=body.maker_notes,
    )
    session.commit()
    return _ser_sub(sub)


class ApprovalRequest(BaseModel):
    operator_id: str
    checker_notes: Optional[str] = None


@router.post("/{submission_id}/approve")
def approve_submission(
    submission_id: str,
    body: ApprovalRequest,
    session: Session = Depends(get_session),
):
    """Checker approves the submission for F2R upload."""
    sub = _get_or_404(session, submission_id)
    if sub.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Not pending approval (current: {sub.status})")
    sub.status = "APPROVED"
    sub.checker_id = body.operator_id
    sub.checker_notes = body.checker_notes
    sub.updated_at = utcnow()
    _add_event(
        session, sub, "APPROVED", body.operator_id,
        from_status="PENDING_APPROVAL", to_status="APPROVED",
        notes=body.checker_notes,
    )
    session.commit()
    return _ser_sub(sub)


class RejectRequest(BaseModel):
    operator_id: str
    rejection_reason: str


@router.post("/{submission_id}/reject")
def reject_submission(
    submission_id: str,
    body: RejectRequest,
    session: Session = Depends(get_session),
):
    """Checker sends the submission back to maker with a reason."""
    sub = _get_or_404(session, submission_id)
    if sub.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Not pending approval (current: {sub.status})")
    sub.status = "CHECKER_REJECTED"
    sub.checker_id = body.operator_id
    sub.checker_notes = body.rejection_reason
    sub.checker_rejected_at = utcnow()
    sub.updated_at = utcnow()
    _add_event(
        session, sub, "CHECKER_REJECTED", body.operator_id,
        from_status="PENDING_APPROVAL", to_status="CHECKER_REJECTED",
        notes=body.rejection_reason,
    )
    session.commit()
    return _ser_sub(sub)


class ConfirmUploadRequest(BaseModel):
    operator_id: str
    portal_ref: str
    notes: Optional[str] = None


@router.post("/{submission_id}/confirm-upload")
def confirm_upload(
    submission_id: str,
    body: ConfirmUploadRequest,
    session: Session = Depends(get_session),
):
    """
    Record that the XML file was manually uploaded to the FINTRAC F2R portal.
    Also updates the linked ComplianceAction to 'filed'.
    """
    sub = _get_or_404(session, submission_id)
    if sub.status != "APPROVED":
        raise HTTPException(status_code=400, detail=f"Must be approved before upload (current: {sub.status})")
    sub.status = "SUBMITTED"
    sub.portal_ref = body.portal_ref
    sub.submitted_at = utcnow()
    sub.updated_at = utcnow()
    _add_event(
        session, sub, "UPLOADED_TO_F2R", body.operator_id,
        from_status="APPROVED", to_status="SUBMITTED",
        notes=body.notes,
        detail={"portal_ref": body.portal_ref},
    )

    # Sync the ComplianceAction to 'filed' with the portal ref
    if sub.action_id:
        action = session.get(ComplianceAction, sub.action_id)
        if action:
            action.status = "filed"
            action.filed_ref = body.portal_ref
            action.updated_at = utcnow()
    elif sub.finding_id:
        action = session.query(ComplianceAction).filter_by(finding_id=sub.finding_id).first()
        if action:
            action.status = "filed"
            action.filed_ref = body.portal_ref
            action.updated_at = utcnow()

    session.commit()
    return _ser_sub(sub)


class AcknowledgeRequest(BaseModel):
    operator_id: str
    ack_number: str
    notes: Optional[str] = None


@router.post("/{submission_id}/acknowledge")
def record_acknowledgement(
    submission_id: str,
    body: AcknowledgeRequest,
    session: Session = Depends(get_session),
):
    """Record the FINTRAC acknowledgement number received from F2R."""
    sub = _get_or_404(session, submission_id)
    if sub.status != "SUBMITTED":
        raise HTTPException(status_code=400, detail=f"Must be submitted first (current: {sub.status})")
    sub.status = "ACKNOWLEDGED"
    sub.ack_number = body.ack_number
    sub.ack_received_at = utcnow()
    sub.updated_at = utcnow()
    _add_event(
        session, sub, "ACKNOWLEDGED", body.operator_id,
        from_status="SUBMITTED", to_status="ACKNOWLEDGED",
        notes=body.notes,
        detail={"ack_number": body.ack_number},
    )
    session.commit()
    return _ser_sub(sub)


class FintracRejectionRequest(BaseModel):
    operator_id: str
    rejection_code: str
    rejection_detail: str


@router.post("/{submission_id}/record-rejection")
def record_fintrac_rejection(
    submission_id: str,
    body: FintracRejectionRequest,
    session: Session = Depends(get_session),
):
    """Record that FINTRAC rejected the filing via F2R."""
    sub = _get_or_404(session, submission_id)
    if sub.status != "SUBMITTED":
        raise HTTPException(status_code=400, detail=f"Must be submitted first (current: {sub.status})")
    sub.status = "FINTRAC_REJECTED"
    sub.fintrac_rejection_code = body.rejection_code
    sub.fintrac_rejection_detail = body.rejection_detail
    sub.updated_at = utcnow()
    _add_event(
        session, sub, "FINTRAC_REJECTED", body.operator_id,
        from_status="SUBMITTED", to_status="FINTRAC_REJECTED",
        notes=body.rejection_detail,
        detail={"code": body.rejection_code},
    )
    session.commit()
    return _ser_sub(sub)


class AmendRequest(BaseModel):
    operator_id: str
    amendment_reason: str


@router.post("/{submission_id}/amend")
def create_amendment(
    submission_id: str,
    body: AmendRequest,
    session: Session = Depends(get_session),
):
    """
    Create a new DRAFT submission as an amendment to a terminal submission
    (ACKNOWLEDGED or FINTRAC_REJECTED).
    The original portal_ref is carried forward as amendment_of_ref.
    """
    original = _get_or_404(session, submission_id)
    if original.status not in ("ACKNOWLEDGED", "FINTRAC_REJECTED"):
        raise HTTPException(
            status_code=400,
            detail=f"Amendments can only be created from ACKNOWLEDGED or FINTRAC_REJECTED submissions (current: {original.status})"
        )

    # Copy report_data and inject amendment fields
    new_data = dict(original.report_data or {})
    new_data["amendment_of_ref"] = original.portal_ref or original.submission_id
    new_data["amendment_reason"] = body.amendment_reason
    new_data["submitted_by"] = body.operator_id
    new_data["approved_by"] = ""
    new_data["filing_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    amendment = EFTRSubmission(
        submission_id=str(uuid.uuid4()),
        finding_id=original.finding_id,
        action_id=original.action_id,
        run_id=original.run_id,
        transaction_id=original.transaction_id,
        status="DRAFT",
        maker_id=body.operator_id,
        report_data=new_data,
        amendment_of_id=original.submission_id,
        amendment_number=(original.amendment_number or 1) + 1,
        amendment_reason=body.amendment_reason,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(amendment)
    _add_event(
        session, amendment, "AMENDMENT_CREATED", body.operator_id,
        to_status="DRAFT",
        notes=body.amendment_reason,
        detail={"amends": original.submission_id, "amendment_number": amendment.amendment_number},
    )
    session.commit()
    return _ser_sub(amendment)


@router.get("/{submission_id}")
def get_submission(submission_id: str, session: Session = Depends(get_session)):
    """Get full submission detail including audit trail."""
    sub = _get_or_404(session, submission_id)
    events = (
        session.query(SubmissionEvent)
        .filter_by(submission_id=submission_id)
        .order_by(SubmissionEvent.created_at.asc())
        .all()
    )
    return {**_ser_sub(sub), "events": [_ser_event(e) for e in events]}


@router.get("")
def list_submissions(
    run_id: Optional[str] = None,
    finding_id: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """List submissions, filtered by run_id and/or finding_id."""
    q = session.query(EFTRSubmission)
    if run_id:
        q = q.filter_by(run_id=run_id)
    if finding_id:
        q = q.filter_by(finding_id=finding_id)
    subs = q.order_by(EFTRSubmission.created_at.desc()).all()
    return [_ser_sub(s) for s in subs]
