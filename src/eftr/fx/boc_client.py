import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx

from config.settings import settings

# BoC Valet API series codes for CAD exchange rates
# Format: FX{CURRENCY}CAD (e.g. FXUSDCAD, FXEURCAD)
BOC_SERIES_TEMPLATE = "FX{currency}CAD"
CACHE_DIR_NAME = "fx_rates"


class BoCFXClient:
    def __init__(self):
        self.base_url = settings.boc_api_base_url
        self.cache_dir = Path(settings.data_processed_dir) / CACHE_DIR_NAME

    def _cache_path(self, currency: str, rate_date: date) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"{currency.upper()}CAD_{rate_date.isoformat()}.json"

    def _load_cache(self, currency: str, rate_date: date) -> Decimal | None:
        path = self._cache_path(currency, rate_date)
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return Decimal(str(data["rate"]))
        return None

    def _save_cache(self, currency: str, rate_date: date, rate: Decimal) -> None:
        path = self._cache_path(currency, rate_date)
        with open(path, "w") as f:
            json.dump({"currency": currency, "date": rate_date.isoformat(), "rate": str(rate)}, f)

    def get_cad_rate(self, currency: str, rate_date: date) -> Decimal:
        """
        Fetch the CAD exchange rate for the given currency on the given date.
        Returns Decimal: 1 unit of currency = X CAD.
        CAD-to-CAD is always 1.0.
        """
        currency = currency.upper()
        if currency == "CAD":
            return Decimal("1.0")

        cached = self._load_cache(currency, rate_date)
        if cached is not None:
            return cached

        series = BOC_SERIES_TEMPLATE.format(currency=currency)
        start = rate_date.isoformat()
        end = rate_date.isoformat()
        url = f"{self.base_url}/observations/{series}/json?start_date={start}&end_date={end}"

        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        observations = data.get("observations", [])
        if not observations:
            # Fall back to the most recent available rate before the date
            url_recent = f"{self.base_url}/observations/{series}/json?recent=1"
            with httpx.Client(timeout=15) as client:
                resp2 = client.get(url_recent)
                resp2.raise_for_status()
                data2 = resp2.json()
            observations = data2.get("observations", [])

        if not observations:
            raise ValueError(f"No BoC FX rate found for {currency} on {rate_date}")

        rate_str = observations[-1].get(series, {}).get("v")
        if rate_str is None:
            raise ValueError(f"Rate value missing in BoC response for {currency} on {rate_date}")

        rate = Decimal(str(rate_str))
        self._save_cache(currency, rate_date, rate)
        return rate

    def convert_to_cad(self, amount: Decimal, currency: str, rate_date: date) -> tuple[Decimal, Decimal]:
        """
        Convert amount in foreign currency to CAD.
        Returns (cad_amount, rate_used).
        """
        rate = self.get_cad_rate(currency, rate_date)
        return (amount * rate).quantize(Decimal("0.0001")), rate
