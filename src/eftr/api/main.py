from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.eftr.api.routers import reconciliation, reports, rules, runs

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
