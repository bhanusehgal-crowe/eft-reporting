"""Base ingestor — pandas-free. Uses csv / openpyxl only."""
import csv
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.utils.hashing import sha256_file
from src.eftr.utils.snapshot import save_snapshot


class BaseIngestor(ABC):
    component = "base_ingestor"

    def __init__(self, session: Session, run_id: str, operator_id: str):
        self.session = session
        self.run_id = run_id
        self.operator_id = operator_id

    def _read_file(self, file_path: Path) -> list[dict]:
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            with open(file_path, newline="", encoding="utf-8-sig") as f:
                return [{k: v.strip() for k, v in row.items()} for row in csv.DictReader(f)]
        elif suffix in (".xlsx", ".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            wb.close()
            if not rows:
                return []
            headers = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
            return [
                {headers[i]: ("" if v is None else str(v).strip()) for i, v in enumerate(row)}
                for row in rows[1:]
            ]
        raise ValueError(f"Unsupported file type: {suffix}")

    def _audit(self, event_type: str, severity: str, message: str, detail: dict | None = None):
        entry = AuditLog(
            log_id=str(uuid.uuid4()),
            run_id=self.run_id,
            event_type=event_type,
            severity=severity,
            component=self.component,
            operator_id=self.operator_id,
            message=message,
            detail=detail or {},
            created_at=datetime.utcnow(),
        )
        self.session.add(entry)
        self.session.flush()

    def _quarantine_row(self, row: dict, error: str) -> None:
        quarantine_dir = Path(settings.data_quarantine_dir)
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        entry = {"run_id": self.run_id, "error": error, "row": row}
        with open(quarantine_dir / f"{self.run_id}_quarantine.jsonl", "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def run(self, file_path: str | Path, run_id: str | None = None) -> list[dict]:
        file_path = Path(file_path)
        if run_id:
            self.run_id = run_id

        file_hash = sha256_file(file_path)
        self._audit("FILE_INGESTED", "INFO", f"Ingesting {file_path.name}",
                    {"file_path": str(file_path), "file_sha256": file_hash})

        raw_rows = self._read_file(file_path)
        valid_rows, quarantine_count = self._validate(raw_rows)

        if quarantine_count:
            self._audit("VALIDATION_ERRORS", "WARN",
                        f"{quarantine_count} rows failed validation and were quarantined",
                        {"quarantine_count": quarantine_count})

        if valid_rows:
            persisted_count = self._persist(valid_rows, file_path)
            snapshot_path = self._snapshot(valid_rows, file_path)
            self._audit("INGEST_COMPLETE", "INFO", f"Persisted {persisted_count} rows",
                        {"persisted_count": persisted_count, "snapshot_path": snapshot_path})

        self.session.commit()
        return valid_rows

    @abstractmethod
    def _validate(self, rows: list[dict]) -> tuple[list[dict], int]:
        """Validate rows, quarantine failures, return (valid_rows, quarantine_count)."""

    @abstractmethod
    def _persist(self, rows: list[dict], source_file: Path) -> int:
        """Persist valid rows to DB; return count persisted."""

    @abstractmethod
    def _snapshot(self, rows: list[dict], source_file: Path) -> str:
        """Write CSV snapshot; return path."""
