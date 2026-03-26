from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.eftr.api.routers import actions, memo, reconciliation, rules, runs, submissions


def _bootstrap():
    """Create directories, initialise DB tables, seed rules if empty."""
    from config.settings import settings
    for d in [
        Path(settings.data_raw_dir) / "eft",
        Path(settings.data_raw_dir) / "reported",
        Path(settings.data_raw_dir) / "uploads",
        Path(settings.data_processed_dir),
        Path(settings.data_exports_dir),
        Path(settings.data_quarantine_dir),
    ]:
        d.mkdir(parents=True, exist_ok=True)

    from config.database import Base, engine
    import src.eftr.models.eft_transaction      # noqa: F401
    import src.eftr.models.reported_transaction  # noqa: F401
    import src.eftr.models.reconciliation        # noqa: F401
    import src.eftr.models.rule                  # noqa: F401
    import src.eftr.models.audit_log             # noqa: F401
    import src.eftr.models.reperformance         # noqa: F401
    import src.eftr.models.action                # noqa: F401
    import src.eftr.models.submission            # noqa: F401
    Base.metadata.create_all(bind=engine)

    try:
        from config.database import SessionLocal
        from src.eftr.models.rule import Rule
        with SessionLocal() as session:
            if session.query(Rule).count() == 0:
                from scripts.seed_rules import seed_rules
                seed_rules()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap()
    yield


app = FastAPI(
    title="EFTR Regulatory Assurance Platform",
    description="FINTRAC EFT compliance validation API",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(actions.router, prefix="/actions", tags=["actions"])
app.include_router(memo.router, prefix="/memo", tags=["memo"])
app.include_router(submissions.router, prefix="/submissions", tags=["submissions"])


@app.get("/health")
def health():
    return {"status": "ok"}
