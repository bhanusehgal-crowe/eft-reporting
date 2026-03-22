from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EFTTransactionIn(BaseModel):
    transaction_id: str
    value_date: date
    settlement_date: date | None = None
    amount: Decimal = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    cad_amount: Decimal | None = None
    cad_conversion_rate: Decimal | None = None
    direction: Literal["INITIATION", "RECEIPT"]
    originator_name: str
    originator_address: str | None = None
    originator_account: str | None = None
    beneficiary_name: str
    beneficiary_address: str | None = None
    beneficiary_account: str | None = None
    counterparty_id: str | None = None
    transaction_type: str | None = None

    @field_validator("currency_code")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def cad_amount_required_for_foreign_currency(self) -> "EFTTransactionIn":
        if self.currency_code != "CAD" and self.cad_amount is None:
            # Will be computed later by FX engine; not a hard error at ingest
            pass
        return self


class ReportedTransactionIn(BaseModel):
    report_reference: str
    reporting_entity_id: str
    reported_transaction_id: str
    report_date: date
    reported_amount: Decimal = Field(gt=0)
    reported_currency: str = Field(min_length=3, max_length=3)
    reported_cad_amount: Decimal | None = None
    report_type: str
    direction: Literal["INITIATION", "RECEIPT"]

    @field_validator("reported_currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.strip().upper()
