from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.eftr.api.routers import reconciliation, reports, rules, runs


def _bootstrap():
    """Create directories, initialise DB tables, seed rules if empty."""
    # Create all mutable data directories (critical on Vercel where /tmp is writable)
    for d in [
        "data/raw/eft", "data/raw/reported", "data/raw/uploads",
        "data/processed", "data/exports", "data/quarantine",
    ]:
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # read-only filesystem on Vercel — settings.py redirects to /tmp

    # Also ensure /tmp paths exist when running on Vercel
    import os
    if os.environ.get("VERCEL") == "1":
        for d in [
            "/tmp/eftr/raw/eft", "/tmp/eftr/raw/reported", "/tmp/eftr/raw/uploads",
            "/tmp/eftr/processed", "/tmp/eftr/exports", "/tmp/eftr/quarantine",
        ]:
            Path(d).mkdir(parents=True, exist_ok=True)

    # Initialise DB tables
    from config.database import Base, engine
    import src.eftr.models.eft_transaction      # noqa: F401
    import src.eftr.models.reported_transaction  # noqa: F401
    import src.eftr.models.reconciliation        # noqa: F401
    import src.eftr.models.rule                  # noqa: F401
    import src.eftr.models.audit_log             # noqa: F401
    import src.eftr.models.reperformance         # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Seed FINTRAC rules if the table is empty
    try:
        from config.database import SessionLocal
        from src.eftr.models.rule import Rule
        with SessionLocal() as session:
            if session.query(Rule).count() == 0:
                from scripts.seed_rules import seed_rules
                seed_rules()
    except Exception:
        pass  # Non-fatal — rules can be seeded manually


app = FastAPI(
    title="EFTR Regulatory Assurance Platform",
    description="FINTRAC EFT compliance validation API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(reconciliation.router, prefix="/runs", tags=["reconciliation"])
app.include_router(rules.router, prefix="/rules", tags=["rules"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])


@app.get("/health")
def health():
    return {"status": "ok"}
