from pathlib import Path

import pandas as pd


def save_snapshot(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def load_snapshot(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


# Legacy aliases kept for any external callers
save_parquet = save_snapshot
load_parquet = load_snapshot
