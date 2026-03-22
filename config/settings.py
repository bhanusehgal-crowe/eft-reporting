from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/eftr.db"
    data_raw_dir: str = "data/raw"
    data_processed_dir: str = "data/processed"
    data_exports_dir: str = "data/exports"
    data_quarantine_dir: str = "data/quarantine"
    log_level: str = "INFO"
    log_file: str = "data/audit.jsonl"
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
