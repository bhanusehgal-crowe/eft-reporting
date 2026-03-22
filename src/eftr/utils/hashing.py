import hashlib
import json
from pathlib import Path


def sha256_row(canonical_fields: dict) -> str:
    """Compute SHA-256 hash of a canonical dict (sorted keys, deterministic)."""
    serialized = json.dumps(canonical_fields, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def sha256_file(file_path: str | Path) -> str:
    """Compute SHA-256 hash of a file on disk."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
