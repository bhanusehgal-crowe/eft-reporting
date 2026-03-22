import sys
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import Base


@pytest.fixture(scope="function")
def in_memory_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(in_memory_engine):
    Session = sessionmaker(bind=in_memory_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def run_id():
    return str(uuid.uuid4())


@pytest.fixture
def operator_id():
    return "test_operator"


@pytest.fixture
def sample_eft_df():
    """20 EFT rows covering all test scenarios."""
    return pd.DataFrame([
        # Clean matches (EFT001-EFT003, EFT005) — will be matched to reported
        {
            "transaction_id": "EFT001", "value_date": date(2026, 3, 1),
            "amount": Decimal("15000"), "currency_code": "CAD", "cad_amount": Decimal("15000"),
            "cad_conversion_rate": Decimal("1.0"), "direction": "INITIATION",
            "originator_name": "Acme Corp", "originator_address": "123 Main St Toronto ON",
            "originator_account": "ACC-1001", "beneficiary_name": "Global Ltd",
            "beneficiary_address": "45 Bay St London UK", "beneficiary_account": "ACC-2001",
        },
        {
            "transaction_id": "EFT004", "value_date": date(2026, 3, 5),
            "amount": Decimal("18000"), "currency_code": "CAD", "cad_amount": Decimal("18000"),
            "cad_conversion_rate": Decimal("1.0"), "direction": "INITIATION",
            "originator_name": "Acme Corp", "originator_address": "123 Main St Toronto ON",
            "originator_account": "ACC-1001", "beneficiary_name": "Euro Transfer GmbH",
            "beneficiary_address": "Berliner Str 10 Berlin", "beneficiary_account": "ACC-2003",
        },
        # Missed report: EFT010, EFT019 — >= $10k, no EFTR
        {
            "transaction_id": "EFT010", "value_date": date(2026, 3, 12),
            "amount": Decimal("13000"), "currency_code": "CAD", "cad_amount": Decimal("13000"),
            "cad_conversion_rate": Decimal("1.0"), "direction": "INITIATION",
            "originator_name": "West Corp", "originator_address": "300 Granville St Vancouver BC",
            "originator_account": "ACC-1006", "beneficiary_name": "Tokyo Corp",
            "beneficiary_address": "Shinjuku 1-1 Tokyo JP", "beneficiary_account": "ACC-2007",
        },
        # Below threshold
        {
            "transaction_id": "EFT020", "value_date": date(2026, 3, 20),
            "amount": Decimal("9500"), "currency_code": "CAD", "cad_amount": Decimal("9500"),
            "cad_conversion_rate": Decimal("1.0"), "direction": "INITIATION",
            "originator_name": "Tech Startup", "originator_address": "Innovation Dr Waterloo ON",
            "originator_account": "ACC-1013", "beneficiary_name": "Silicon Corp",
            "beneficiary_address": "101 Castro St Mountain View CA", "beneficiary_account": "ACC-2011",
        },
    ])


@pytest.fixture
def sample_reported_df():
    """Reported transactions — partially complete."""
    return pd.DataFrame([
        {
            "reported_id": str(uuid.uuid4()),
            "report_reference": "RPT-001", "reporting_entity_id": "MAPLE-BANK",
            "reported_transaction_id": "EFT001", "report_date": date(2026, 3, 3),
            "reported_amount": Decimal("15000"), "reported_currency": "CAD",
            "reported_cad_amount": Decimal("15000"), "report_type": "EFTR", "direction": "INITIATION",
        },
        {
            "reported_id": str(uuid.uuid4()),
            "report_reference": "RPT-020", "reporting_entity_id": "MAPLE-BANK",
            "reported_transaction_id": "EFT020", "report_date": date(2026, 3, 22),
            "reported_amount": Decimal("9500"), "reported_currency": "CAD",
            "reported_cad_amount": Decimal("9500"), "report_type": "EFTR", "direction": "INITIATION",
        },
    ])
