from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config.database import get_session
from src.eftr.models.audit_log import AuditLog
from src.eftr.models.reconciliation import ReconciliationResult, ReconciliationRun

router = APIRouter()


@router.get("/{run_id}/reconciliation")
def get_reconciliation(
    run_id: str,
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    run = session.get(ReconciliationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    query = session.query(ReconciliationResult).filter_by(run_id=run_id)
    if status:
        query = query.filter(ReconciliationResult.status == status.upper())

    total = query.count()
    results = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "run_id": run_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [
            {
                "result_id": r.result_id,
                "status": r.status,
                "eft_transaction_id": r.eft_transaction_id,
                "reported_id": r.reported_id,
                "match_method": r.match_method,
                "variance_amount": float(r.variance_amount) if r.variance_amount else None,
                "detail": r.detail,
            }
            for r in results
        ],
    }


@router.get("/{run_id}/findings")
def get_findings(
    run_id: str,
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    from src.eftr.models.rule import RuleFinding

    run = session.get(ReconciliationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    query = session.query(RuleFinding).filter_by(run_id=run_id)
    if severity:
        query = query.filter(RuleFinding.severity == severity.upper())

    total = query.count()
    findings = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "run_id": run_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "findings": [
            {
                "finding_id": f.finding_id,
                "rule_code": f.rule_code,
                "rule_version": f.rule_version,
                "severity": f.severity,
                "transaction_id": f.transaction_id,
                "detail": f.detail,
                "created_at": f.created_at,
            }
            for f in findings
        ],
    }


@router.get("/{run_id}/audit")
def get_audit_log(
    run_id: str,
    severity: str | None = Query(None),
    page_size: int = Query(200, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    run = session.get(ReconciliationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    query = session.query(AuditLog).filter_by(run_id=run_id)
    if severity:
        query = query.filter(AuditLog.severity == severity.upper())
    query = query.order_by(AuditLog.created_at)

    entries = query.limit(page_size).all()
    return {
        "run_id": run_id,
        "entries": [
            {
                "log_id": e.log_id,
                "event_type": e.event_type,
                "severity": e.severity,
                "component": e.component,
                "operator_id": e.operator_id,
                "message": e.message,
                "detail": e.detail,
                "created_at": e.created_at,
            }
            for e in entries
        ],
    }


@router.get("/{run_id}/reperformance")
def get_reperformance(
    run_id: str,
    session: Session = Depends(get_session),
):
    from src.eftr.models.reperformance import ReperformanceResult

    run = session.get(ReconciliationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    results = session.query(ReperformanceResult).filter_by(run_id=run_id).all()

    return {
        "run_id": run_id,
        "results": [
            {
                "result_id": r.result_id,
                "calculation_type": r.calculation_type,
                "status": r.status,
                "reported_value": float(r.reported_value) if r.reported_value else None,
                "reperformed_value": float(r.reperformed_value) if r.reperformed_value else None,
                "variance_absolute": float(r.variance_absolute) if r.variance_absolute else None,
                "variance_pct": float(r.variance_pct) if r.variance_pct else None,
                "detail": r.detail,
            }
            for r in results
        ],
    }
