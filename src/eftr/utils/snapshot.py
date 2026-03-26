"""CSV snapshot helpers — pandas-free."""
import csv
from pathlib import Path


def save_snapshot(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if v is None else str(v)) for k, v in row.items()})


def load_snapshot(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# Legacy aliases
save_parquet = save_snapshot
load_parquet = load_snapshot
