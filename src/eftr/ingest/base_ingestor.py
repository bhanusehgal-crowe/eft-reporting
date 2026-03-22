import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import ValidationError
from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.models.audit_log import AuditLog
from src.eftr.utils.hashing import sha256_file
from src.eftr.utils.snapshot import save_parquet


class BaseIngestor(ABC):
    component = "base_ingestor"

    def __init__(self, session: Session, run_id: str, operator_id: str):
        self.session = session
        self.run_id = run_id
        self.operator_id = operator_id

    def _read_file(self, file_path: Path) -> pd.DataFrame:
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(file_path, dtype=str, keep_default_na=False)
        elif suffix in (".xlsx", ".xls"):
            return pd.read_excel(file_path, dtype=str, keep_default_na=False)
        else:
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
        import json

        entry = {"run_id": self.run_id, "error": error, "row": row}
        with open(quarantine_dir / f"{self.run_id}_quarantine.jsonl", "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def run(self, file_path: str | Path, run_id: str | None = None) -> pd.DataFrame:
        file_path = Path(file_path)
        if run_id:
            self.run_id = run_id

        file_hash = sha256_file(file_path)
        self._audit(
            "FILE_INGESTED",
            "INFO",
            f"Ingesting {file_path.name}",
            {"file_path": str(file_path), "file_sha256": file_hash},
        )

        raw_df = self._read_file(file_path)
        validated_df, quarantine_count = self._validate(raw_df)

        if quarantine_count:
            self._audit(
                "VALIDATION_ERRORS",
                "WARN",
                f"{quarantine_count} rows failed validation and were quarantined",
                {"quarantine_count": quarantine_count},
            )

        if not validated_df.empty:
            persisted_count = self._persist(validated_df, file_path)
            snapshot_path = self._snapshot(validated_df, file_path)
            self._audit(
                "INGEST_COMPLETE",
                "INFO",
                f"Persisted {persisted_count} rows",
                {"persisted_count": persisted_count, "snapshot_path": snapshot_path},
            )

        self.session.commit()
        return validated_df

    @abstractmethod
    def _validate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Validate rows, quarantine failures, return (valid_df, quarantine_count)."""

    @abstractmethod
    def _persist(self, df: pd.DataFrame, source_file: Path) -> int:
        """Persist valid rows to DB; return count persisted (skip duplicates)."""

    @abstractmethod
    def _snapshot(self, df: pd.DataFrame, source_file: Path) -> str:
        """Write parquet snapshot; return path."""
