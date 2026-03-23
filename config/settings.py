import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# On Vercel the repo filesystem is read-only; use /tmp for mutable data.
_ON_VERCEL = os.environ.get("VERCEL") == "1"
_DATA_ROOT = "/tmp/eftr" if _ON_VERCEL else "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # When running on Vercel set DATABASE_URL to your Vercel Postgres connection
    # string (postgres://...).  Omit it locally to use SQLite.
    database_url: str = (
        f"sqlite:///{_DATA_ROOT}/eftr.db" if not os.environ.get("DATABASE_URL") else os.environ["DATABASE_URL"]
    )
    data_raw_dir: str = f"{_DATA_ROOT}/raw"
    data_processed_dir: str = f"{_DATA_ROOT}/processed"
    data_exports_dir: str = f"{_DATA_ROOT}/exports"
    data_quarantine_dir: str = f"{_DATA_ROOT}/quarantine"
    log_level: str = "INFO"
    log_file: str = f"{_DATA_ROOT}/audit.jsonl"
    boc_api_base_url: str = "https://www.bankofcanada.ca/valet"
    default_province: str = "ON"

    def raw_eft_dir(self) -> Path:
        return Path(self.data_raw_dir) / "eft"

    def raw_reported_dir(self) -> Path:
        return Path(self.data_raw_dir) / "reported"

    def processed_dir(self) -> Path:
        return Path(self.data_processed_dir)

    def exports_dir(self) -> Path:
        return Path(self.data_exports_dir)

    def quarantine_dir(self) -> Path:
        return Path(self.data_quarantine_dir)


settings = Settings()
