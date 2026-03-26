import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_session
from config.settings import settings
from src.eftr.models.reconciliation import ReconciliationResult, ReconciliationRun
from src.eftr.models.rule import RuleFinding
from src.eftr.utils.datetime_utils import utcnow

router = APIRouter()


class CreateRunRequest(BaseModel):
    eft_file: str
    reported_file: str


class RunResponse(BaseModel):
    run_id: str
    status: str
    triggered_by: str
    operator_id: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    parameters: dict

    class Config:
        from_attributes = True


def _get_operator(x_operator_id: Optional[str] = Header(None)) -> str:
    if not x_operator_id:
        raise HTTPException(status_code=400, detail="X-Operator-ID header is required")
    return x_operator_id


@router.post("/upload", status_code=200)
async def upload_and_run(
    eft_file: UploadFile = File(...),
    reported_file: UploadFile = File(...),
    operator_id: str = Form(...),
    session: Session = Depends(get_session),
):
    """
    Accept two CSV uploads, save to /tmp, run the full pipeline synchronously,
    and return when complete.  Synchronous execution is required for Vercel
    serverless (background tasks are killed when the response returns).
    """
    run_id = str(uuid.uuid4())

    upload_dir = Path(settings.data_raw_dir) / "uploads" / run_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    eft_path = upload_dir / (eft_file.filename or "eft.csv")
    rep_path = upload_dir / (reported_file.filename or "reported.csv")

    eft_path.write_bytes(await eft_file.read())
    rep_path.write_bytes(await reported_file.read())

    run = ReconciliationRun(
        run_id=run_id,
        status="PENDING",
        triggered_by="upload",
        operator_id=operator_id,
        started_at=None,
        parameters={"eft_file": str(eft_path), "reported_file": str(rep_path)},
        created_at=utcnow(),
    )
    session.add(run)
    session.commit()

    # Run synchronously so the result is available when we return
    _run_pipeline(run_id, str(eft_path), str(rep_path), operator_id)

    # Query all results on THIS instance while the DB is fresh.
    # This avoids Vercel's multi-instance problem (different instances have
    # separate /tmp filesystems with separate SQLite DBs).
    from config.database import SessionLocal as _SL
    from src.eftr.models.audit_log import AuditLog
    from src.eftr.models.action import ComplianceAction
    from src.eftr.api.routers.memo import generate_memo
    with _SL() as s:
        run_obj = s.get(ReconciliationRun, run_id)
        recon_results = s.query(ReconciliationResult).filter_by(run_id=run_id).all()
        rule_findings = s.query(RuleFinding).filter_by(run_id=run_id).all()
        audit_entries = s.query(AuditLog).filter_by(run_id=run_id).order_by(AuditLog.created_at).all()
        action_entries = s.query(ComplianceAction).filter_by(run_id=run_id).all()

        status = run_obj.status if run_obj else "FAILED"
        err = (run_obj.parameters or {}).get("error") if run_obj else None

        try:
            memo_data = generate_memo(run_id, s)
        except Exception:
            memo_data = None

        return {
            "run_id": run_id,
            "status": status,
            "error": err,
            "run": {
                "run_id": run_id,
                "status": status,
                "triggered_by": "upload",
                "operator_id": operator_id,
                "started_at": run_obj.started_at.isoformat() if run_obj and run_obj.started_at else None,
                "completed_at": run_obj.completed_at.isoformat() if run_obj and run_obj.completed_at else None,
                "parameters": run_obj.parameters if run_obj else {},
            },
            "reconciliation": [
                {
                    "result_id": r.result_id,
                    "status": r.status,
                    "eft_transaction_id": r.eft_transaction_id,
                    "reported_id": r.reported_id,
                    "match_method": r.match_method,
                    "variance_amount": float(r.variance_amount) if r.variance_amount else None,
                    "detail": r.detail,
                }
                for r in recon_results
            ],
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "rule_code": f.rule_code,
                    "rule_version": f.rule_version,
                    "severity": f.severity,
                    "transaction_id": f.transaction_id,
                    "detail": f.detail,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in rule_findings
            ],
            "audit_log": [
                {
                    "log_id": e.log_id,
                    "event_type": e.event_type,
                    "severity": e.severity,
                    "component": e.component,
                    "operator_id": e.operator_id,
                    "message": e.message,
                    "detail": e.detail,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in audit_entries
            ],
            "actions": [
                {
                    "action_id": a.action_id,
                    "finding_id": a.finding_id,
                    "run_id": a.run_id,
                    "status": a.status,
                    "operator_id": a.operator_id,
                    "notes": a.notes,
                    "filed_ref": a.filed_ref,
                    "decision": a.decision,
                    "deadline": a.deadline.isoformat() if a.deadline else None,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                }
                for a in action_entries
            ],
            "memo": memo_data,
        }


@router.post("", status_code=202)
def create_run(
    request: CreateRunRequest,
    background_tasks: BackgroundTasks,
    operator_id: str = Depends(_get_operator),
    session: Session = Depends(get_session),
):
    run_id = str(uuid.uuid4())
    run = ReconciliationRun(
        run_id=run_id,
        status="PENDING",
        triggered_by="api",
        operator_id=operator_id,
        started_at=None,
        parameters={"eft_file": request.eft_file, "reported_file": request.reported_file},
        created_at=utcnow(),
    )
    session.add(run)
    session.commit()

    # Trigger pipeline in background
    background_tasks.add_task(
        _run_pipeline,
        run_id,
        request.eft_file,
        request.reported_file,
        operator_id,
    )

    return {"run_id": run_id, "status": "PENDING"}


def _run_pipeline(run_id: str, eft_file: str, reported_file: str, operator_id: str):
    from config.database import SessionLocal
    from src.eftr.ingest.eft_ingestor import EFTIngestor
    from src.eftr.ingest.reported_ingestor import ReportedIngestor
    from src.eftr.reconciliation.aggregation import AggregationEngine
    from src.eftr.reconciliation.engine import ReconciliationEngine
    from src.eftr.rules.engine import RulesEngine

    with SessionLocal() as session:
        run = session.get(ReconciliationRun, run_id)
        run.status = "RUNNING"
        run.started_at = utcnow()
        session.commit()

        try:
            EFTIngestor(session, run_id, operator_id).run(eft_file)
            ReportedIngestor(session, run_id, operator_id).run(reported_file)
            ReconciliationEngine(session, run_id, operator_id).run()
            AggregationEngine(session, run_id, operator_id).run()
            RulesEngine(session, run_id, operator_id).run()

            run.status = "COMPLETED"
            run.completed_at = utcnow()
        except Exception as exc:
            import traceback
            run.status = "FAILED"
            run.completed_at = utcnow()
            run.parameters = {**run.parameters, "error": str(exc), "traceback": traceback.format_exc()}
        session.commit()


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(ReconciliationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    matched = session.query(ReconciliationResult).filter_by(run_id=run_id, status="MATCHED").count()
    missed = session.query(ReconciliationResult).filter_by(run_id=run_id, status="MISSED").count()
    phantom = session.query(ReconciliationResult).filter_by(run_id=run_id, status="PHANTOM").count()
    breaches = session.query(RuleFinding).filter_by(run_id=run_id, severity="BREACH").count()
    warns = session.query(RuleFinding).filter_by(run_id=run_id, severity="WARN").count()

    return {
        "run_id": run.run_id,
        "status": run.status,
        "triggered_by": run.triggered_by,
        "operator_id": run.operator_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "parameters": {
            **run.parameters,
            "summary": {
                "matched": matched,
                "missed": missed,
                "phantom": phantom,
                "breaches": breaches,
                "warns": warns,
            },
        },
    }


@router.get("")
def list_runs(session: Session = Depends(get_session)):
    runs = session.query(ReconciliationRun).order_by(ReconciliationRun.created_at.desc()).limit(50).all()
    return [
        {
            "run_id": r.run_id,
            "status": r.status,
            "operator_id": r.operator_id,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
        }
        for r in runs
    ]
