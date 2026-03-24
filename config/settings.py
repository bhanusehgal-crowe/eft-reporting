import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# On Vercel, only /tmp is writable. VERCEL=1 is set automatically by the platform.
_base = "/tmp" if os.getenv("VERCEL") else "."


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = f"sqlite:///{_base}/eftr.db"
    data_raw_dir: str = f"{_base}/data/raw"
    data_processed_dir: str = f"{_base}/data/processed"
    data_exports_dir: str = f"{_base}/data/exports"
    data_quarantine_dir: str = f"{_base}/data/quarantine"
    log_level: str = "INFO"
    log_file: str = f"{_base}/data/audit.jsonl"
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
