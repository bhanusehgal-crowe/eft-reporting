from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_session
from config.settings import settings
from src.eftr.models.audit_log import AuditLog

router = APIRouter()


@router.get("/{run_id}/missed-transactions")
def download_missed_transactions(run_id: str, session: Session = Depends(get_session)):
    """Download the most recent missed transactions Excel report for a run."""
    exports_dir = Path(settings.data_exports_dir)
    if not exports_dir.exists():
        raise HTTPException(status_code=404, detail="No reports directory found")

    # Find latest report for this run
    matching = sorted(
        exports_dir.glob(f"missed_transactions_{run_id}_*.xlsx"), reverse=True
    )
    if not matching:
        raise HTTPException(status_code=404, detail=f"No report found for run {run_id}")

    report_path = matching[0]
    return FileResponse(
        path=str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=report_path.name,
    )
