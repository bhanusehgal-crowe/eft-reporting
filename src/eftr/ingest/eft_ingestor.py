"""EFT ingestor — pandas-free."""
import json
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.ingest.base_ingestor import BaseIngestor
from src.eftr.ingest.validators import EFTTransactionIn
from src.eftr.models.eft_transaction import EFTTransaction
from src.eftr.utils.hashing import sha256_row
from src.eftr.utils.snapshot import save_snapshot


def _to_json_safe(d: dict) -> dict:
    return json.loads(json.dumps(d, default=str))


def _empty(v) -> bool:
    return v is None or str(v).strip() in ("", "None", "nan", "NaN")


class EFTIngestor(BaseIngestor):
    component = "eft_ingestor"

    EFT_HASH_FIELDS = [
        "transaction_id", "value_date", "amount", "currency_code",
        "direction", "originator_name", "beneficiary_name",
    ]
    OPTIONAL_NUMERIC = ["cad_amount", "cad_conversion_rate", "settlement_date"]

    def _clean_row(self, row: dict) -> dict:
        for key in self.OPTIONAL_NUMERIC:
            if _empty(row.get(key)):
                row[key] = None
        return row

    def _validate(self, rows: list[dict]) -> tuple[list[dict], int]:
        valid_rows, quarantine_count = [], 0
        for row in rows:
            row = self._clean_row(dict(row))
            try:
                validated = EFTTransactionIn(**row)
                valid_rows.append(validated.model_dump())
            except (ValidationError, Exception) as exc:
                quarantine_count += 1
                self._quarantine_row(row, str(exc))
                self._audit("ROW_QUARANTINED", "WARN", f"Row quarantined: {exc}",
                            {"transaction_id": row.get("transaction_id"), "error": str(exc)})
        return valid_rows, quarantine_count

    def _persist(self, rows: list[dict], source_file: Path) -> int:
        count = 0
        for row in rows:
            canonical = {k: row.get(k) for k in self.EFT_HASH_FIELDS}
            row_hash = sha256_row(canonical)

            existing = self.session.execute(
                select(EFTTransaction).where(EFTTransaction.row_hash == row_hash)
            ).first()
            if existing:
                continue

            cad_amount = row.get("cad_amount")
            if cad_amount is None:
                cad_amount = row["amount"]

            tx = EFTTransaction(
                transaction_id=str(row["transaction_id"]),
                run_id=self.run_id,
                source_file=str(source_file),
                row_hash=row_hash,
                value_date=row["value_date"],
                settlement_date=row.get("settlement_date"),
                amount=Decimal(str(row["amount"])),
                currency_code=str(row["currency_code"]).upper(),
                cad_amount=Decimal(str(cad_amount)),
                cad_conversion_rate=row.get("cad_conversion_rate"),
                direction=row["direction"],
                originator_name=str(row["originator_name"]),
                originator_address=row.get("originator_address"),
                originator_account=row.get("originator_account"),
                beneficiary_name=str(row["beneficiary_name"]),
                beneficiary_address=row.get("beneficiary_address"),
                beneficiary_account=row.get("beneficiary_account"),
                counterparty_id=row.get("counterparty_id"),
                transaction_type=row.get("transaction_type"),
                raw_payload=_to_json_safe(row),
            )
            self.session.add(tx)
            count += 1
        return count

    def _snapshot(self, rows: list[dict], source_file: Path) -> str:
        snapshot_dir = Path(settings.data_processed_dir) / "eft"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = snapshot_dir / f"{self.run_id}_eft.csv"
        save_snapshot(rows, path)
        return str(path)
