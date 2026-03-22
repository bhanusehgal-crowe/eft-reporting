import json
import uuid
from decimal import Decimal
from pathlib import Path

import pandas as pd
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session


def _to_json_safe(d: dict) -> dict:
    return json.loads(json.dumps(d, default=str))

from config.settings import settings
from src.eftr.ingest.base_ingestor import BaseIngestor
from src.eftr.ingest.validators import ReportedTransactionIn
from src.eftr.models.reported_transaction import ReportedTransaction
from src.eftr.utils.hashing import sha256_row
from src.eftr.utils.snapshot import save_parquet


class ReportedIngestor(BaseIngestor):
    component = "reported_ingestor"

    REPORTED_HASH_FIELDS = [
        "report_reference",
        "reported_transaction_id",
        "report_date",
        "reported_amount",
        "reported_currency",
        "direction",
    ]

    def _validate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        valid_rows = []
        quarantine_count = 0
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            try:
                validated = ReportedTransactionIn(**row_dict)
                valid_rows.append(validated.model_dump())
            except (ValidationError, Exception) as exc:
                quarantine_count += 1
                self._quarantine_row(row_dict, str(exc))
                self._audit(
                    "ROW_QUARANTINED",
                    "WARN",
                    f"Row quarantined: {exc}",
                    {
                        "report_reference": row_dict.get("report_reference"),
                        "error": str(exc),
                    },
                )
        return pd.DataFrame(valid_rows), quarantine_count

    def _persist(self, df: pd.DataFrame, source_file: Path) -> int:
        count = 0
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            canonical = {k: row_dict.get(k) for k in self.REPORTED_HASH_FIELDS}
            row_hash = sha256_row(canonical)

            existing = self.session.execute(
                select(ReportedTransaction).where(ReportedTransaction.row_hash == row_hash)
            ).first()
            if existing:
                continue

            rt = ReportedTransaction(
                reported_id=str(uuid.uuid4()),
                run_id=self.run_id,
                source_file=str(source_file),
                row_hash=row_hash,
                report_reference=str(row_dict["report_reference"]),
                reporting_entity_id=str(row_dict["reporting_entity_id"]),
                reported_transaction_id=str(row_dict["reported_transaction_id"]),
                report_date=row_dict["report_date"],
                reported_amount=Decimal(str(row_dict["reported_amount"])),
                reported_currency=str(row_dict["reported_currency"]).upper(),
                reported_cad_amount=(
                    Decimal(str(row_dict["reported_cad_amount"]))
                    if row_dict.get("reported_cad_amount")
                    else None
                ),
                report_type=str(row_dict["report_type"]),
                direction=row_dict["direction"],
                raw_payload=_to_json_safe(row_dict),
            )
            self.session.add(rt)
            count += 1
        return count

    def _snapshot(self, df: pd.DataFrame, source_file: Path) -> str:
        snapshot_dir = Path(settings.data_processed_dir) / "reported"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = snapshot_dir / f"{self.run_id}_reported.parquet"
        save_parquet(df, path)
        return str(path)
