import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import settings
from src.eftr.ingest.base_ingestor import BaseIngestor
from src.eftr.ingest.validators import EFTTransactionIn
from src.eftr.models.eft_transaction import EFTTransaction
from src.eftr.utils.hashing import sha256_row
from src.eftr.utils.snapshot import save_parquet


def _to_json_safe(d: dict) -> dict:
    """Convert a dict to be JSON-serializable (dates, Decimals → str)."""
    return json.loads(json.dumps(d, default=str))


class EFTIngestor(BaseIngestor):
    component = "eft_ingestor"

    EFT_HASH_FIELDS = [
        "transaction_id",
        "value_date",
        "amount",
        "currency_code",
        "direction",
        "originator_name",
        "beneficiary_name",
    ]

    OPTIONAL_NUMERIC = ["cad_amount", "cad_conversion_rate", "settlement_date"]

    def _clean_row(self, row_dict: dict) -> dict:
        """Convert empty strings to None for optional fields."""
        for key in self.OPTIONAL_NUMERIC:
            val = row_dict.get(key)
            if val == "" or (isinstance(val, float) and pd.isna(val)):
                row_dict[key] = None
        return row_dict

    def _validate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        valid_rows = []
        quarantine_count = 0
        for _, row in df.iterrows():
            row_dict = self._clean_row(row.to_dict())
            try:
                validated = EFTTransactionIn(**row_dict)
                valid_rows.append(validated.model_dump())
            except (ValidationError, Exception) as exc:
                quarantine_count += 1
                self._quarantine_row(row_dict, str(exc))
                self._audit(
                    "ROW_QUARANTINED",
                    "WARN",
                    f"Row quarantined: {exc}",
                    {"transaction_id": row_dict.get("transaction_id"), "error": str(exc)},
                )
        return pd.DataFrame(valid_rows), quarantine_count

    def _persist(self, df: pd.DataFrame, source_file: Path) -> int:
        count = 0
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            canonical = {k: row_dict.get(k) for k in self.EFT_HASH_FIELDS}
            row_hash = sha256_row(canonical)

            # Skip duplicate row hashes
            existing = self.session.execute(
                select(EFTTransaction).where(EFTTransaction.row_hash == row_hash)
            ).first()
            if existing:
                continue

            # Default cad_amount to amount if currency is CAD
            cad_amount = row_dict.get("cad_amount")
            if cad_amount is None or (isinstance(cad_amount, float) and pd.isna(cad_amount)):
                if str(row_dict.get("currency_code", "")).upper() == "CAD":
                    cad_amount = row_dict["amount"]
                else:
                    cad_amount = row_dict["amount"]  # placeholder until FX engine runs

            tx = EFTTransaction(
                transaction_id=str(row_dict["transaction_id"]),
                run_id=self.run_id,
                source_file=str(source_file),
                row_hash=row_hash,
                value_date=row_dict["value_date"],
                settlement_date=row_dict.get("settlement_date"),
                amount=Decimal(str(row_dict["amount"])),
                currency_code=str(row_dict["currency_code"]).upper(),
                cad_amount=Decimal(str(cad_amount)),
                cad_conversion_rate=row_dict.get("cad_conversion_rate"),
                direction=row_dict["direction"],
                originator_name=str(row_dict["originator_name"]),
                originator_address=row_dict.get("originator_address"),
                originator_account=row_dict.get("originator_account"),
                beneficiary_name=str(row_dict["beneficiary_name"]),
                beneficiary_address=row_dict.get("beneficiary_address"),
                beneficiary_account=row_dict.get("beneficiary_account"),
                counterparty_id=row_dict.get("counterparty_id"),
                transaction_type=row_dict.get("transaction_type"),
                raw_payload=_to_json_safe(row_dict),
            )
            self.session.add(tx)
            count += 1
        return count

    def _snapshot(self, df: pd.DataFrame, source_file: Path) -> str:
        snapshot_dir = Path(settings.data_processed_dir) / "eft"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = snapshot_dir / f"{self.run_id}_eft.csv"
        save_parquet(df, path)
        return str(path)
