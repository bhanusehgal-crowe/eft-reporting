# EFTR Regulatory Assurance Platform — Project Handoff

## What This Is

A FINTRAC compliance validation platform for Canadian Electronic Funds Transfer (EFT) reporting. It ingests raw EFT transaction data alongside filed EFTR reports, runs reconciliation and rule checks, and surfaces breaches in a live dashboard.

**Regulatory context:** FINTRAC requires reporting entities (banks, MSBs) to file an EFTR within **5 business days** for any international EFT of **CAD $10,000 or more**, or multiple EFTs aggregating to $10,000+ within a **24-hour window**.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.11 |
| Data processing | pandas, pyarrow |
| Validation | Pydantic v2 |
| ORM / DB | SQLAlchemy 2.x + SQLite (local) |
| Logging | structlog (JSON) |
| API | FastAPI + uvicorn |
| FX rates | Bank of Canada Valet API |
| Frontend | Next.js 14 (React, TypeScript) |
| Charts | Chart.js + react-chartjs-2 |
| Frontend hosting | Vercel |
| Backend hosting | Render (in progress — see Deployment Status) |

---

## Repository

**GitHub:** `https://github.com/bhanusehgal-crowe/eft-reporting`
**Branch:** `main`

---

## Project Structure

```
EFTR-AI-Use-Case/
├── config/
│   ├── settings.py          # Pydantic-settings — all env config
│   ├── database.py          # SQLAlchemy engine + session factory
│   └── logging.py           # structlog JSON renderer
│
├── src/eftr/
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── eft_transaction.py
│   │   ├── reported_transaction.py
│   │   ├── reconciliation.py
│   │   ├── rule.py
│   │   ├── audit_log.py
│   │   └── reperformance.py
│   ├── ingest/              # CSV/Excel → DB pipeline
│   │   ├── eft_ingestor.py
│   │   ├── reported_ingestor.py
│   │   └── validators.py    # Pydantic field schemas
│   ├── reconciliation/      # Tiered matching engine
│   │   ├── engine.py        # Tier 1 (exact ID) + Tier 2 (fuzzy)
│   │   ├── aggregation.py   # 24-hour window grouping
│   │   └── report.py        # Excel report generator
│   ├── rules/               # FINTRAC rule evaluation
│   │   ├── engine.py
│   │   ├── registry.py
│   │   └── handlers/        # One file per rule type
│   ├── reperformance/       # Phase 2: recalculate reported values
│   │   └── engine.py
│   ├── fx/
│   │   └── boc_client.py    # Bank of Canada Valet API + cache
│   ├── api/
│   │   ├── main.py          # FastAPI app + startup bootstrap
│   │   └── routers/
│   │       ├── runs.py      # POST /runs/upload, GET /runs
│   │       ├── reconciliation.py
│   │       ├── rules.py
│   │       └── reports.py
│   └── utils/
│       ├── business_days.py # Canadian holiday calendar
│       ├── hashing.py       # SHA-256 row dedup
│       └── datetime_utils.py
│
├── scripts/
│   ├── run_phase1.py        # CLI: ingest → reconcile → rules → report
│   ├── run_phase2.py        # CLI: reperformance engine
│   ├── seed_rules.py        # Seeds 7 FINTRAC rules into DB
│   └── seed_demo_data.py    # Populates DB with demo scenarios
│
├── tests/
│   ├── conftest.py
│   ├── unit/                # 20 passing unit tests
│   ├── integration/         # 2 passing integration tests
│   └── fixtures/
│       ├── sample_eft.csv       # 20 EFT rows (all demo scenarios)
│       ├── sample_reported.csv  # 13 EFTR rows (intentionally incomplete)
│       └── seed_rules.yaml      # 7 canonical FINTRAC rules
│
├── dashboard/               # Next.js frontend (deployed to Vercel)
│   ├── app/
│   │   ├── page.tsx         # Single-page React app (all 5 sections)
│   │   └── layout.tsx       # Bootstrap 5 + Bootstrap Icons from CDN
│   ├── next.config.js
│   ├── vercel.json          # Tells Vercel this is a Next.js project
│   └── package.json
│
├── migrations/              # Alembic schema migrations
│   └── versions/001_initial_schema.py
│
├── dashboard.html           # Standalone HTML dashboard (no build needed)
├── render.yaml              # Render deployment config
├── runtime.txt              # Python 3.11 for Render
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project metadata + dev deps
└── .env.example             # Environment variable template
```

---

## Environment Variables

Create a `.env` file at the repo root (copy from `.env.example`):

```env
DATABASE_URL=sqlite:///./data/eftr.db
DATA_RAW_DIR=data/raw
DATA_PROCESSED_DIR=data/processed
LOG_LEVEL=INFO
```

---

## Running Locally

### 1. Python backend

```bash
# Install dependencies
pip install -r requirements.txt

# Initialise DB and seed FINTRAC rules
python scripts/seed_rules.py

# Start the API server
uvicorn src.eftr.api.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 2. Run a compliance analysis

```bash
# Against the demo fixture CSVs
python scripts/run_phase1.py \
  --eft tests/fixtures/sample_eft.csv \
  --reported tests/fixtures/sample_reported.csv \
  --operator your.name

# Or seed a full demo dataset
python scripts/seed_demo_data.py --reset
```

### 3. View the standalone dashboard

Open `dashboard.html` in your browser while the API is running on `localhost:8000`. No build step required.

### 4. Next.js dashboard (local)

```bash
cd dashboard
npm install
npm run dev
# → http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `dashboard/.env.local`.

### 5. Run tests

```bash
pytest          # 22 tests, all passing
pytest -v       # verbose
```

---

## Deployment Status

### Frontend — Vercel ✅ LIVE

| Item | Value |
|---|---|
| URL | `https://eft-reporting-bhanu-sehgals-projects.vercel.app` |
| Project | `eft-reporting` in Vercel team `bhanu-sehgals-projects` |
| Root Directory | `dashboard/` |
| Auto-deploy | Yes — every push to `main` |
| `NEXT_PUBLIC_API_URL` | Currently set to `https://eftr-api.onrender.com` |

### Backend — Render ⚠️ BUILD FAILING

| Item | Value |
|---|---|
| Service | `eftr-api` |
| URL (once live) | `https://eftr-api.onrender.com` |
| Dashboard | `https://dashboard.render.com/web/srv-d70ak84hg0os73a7vncg` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn src.eftr.api.main:app --host 0.0.0.0 --port $PORT` |

**The backend service exists on Render but the build is failing with exit code 1.**
The error is not yet identified — the Render API does not expose raw build logs.

**To diagnose:** Go to the Render dashboard → `eftr-api` → click the failed deploy → **Logs** tab → scroll to the error. The most likely cause is one of the heavier Python packages (`pyarrow`, `pandas`) failing to install on the build environment.

**To fix:** Identify the failing package from the Render build logs and either pin it to a version that has pre-built wheels, or replace it with a lighter equivalent. Once fixed, auto-deploy will pick up the next `git push` to `main`.

---

## FINTRAC Rules Seeded

| Rule Code | Severity | Description |
|---|---|---|
| `FINTRAC_SINGLE_THRESHOLD` | BREACH | Single EFT ≥ CAD $10,000 not reported |
| `FINTRAC_24HR_AGGREGATION` | BREACH | Aggregated EFTs ≥ $10,000 in 24h not reported |
| `FINTRAC_FILING_DEADLINE` | BREACH | EFTR filed > 5 business days after transaction |
| `FINTRAC_MANDATORY_FIELDS` | WARN | Required FINTRAC fields missing from report |
| `FINTRAC_TRAVEL_RULE` | WARN | Originator or beneficiary info missing |
| `FINTRAC_FX_CONVERSION` | WARN | CAD amount not derived from BoC rate |
| `FINTRAC_OVER_REPORTING` | INFO | EFTR filed for EFT below $10,000 threshold |

---

## Dashboard Sections

The Next.js dashboard (`dashboard/app/page.tsx`) is a single `"use client"` React component with 5 sections navigated via sidebar:

| Section | What it shows |
|---|---|
| **Overview** | Run summary, breach alert banner, metric cards, doughnut + bar charts, run history table |
| **Missed Transactions** | EFTs with no EFTR filed; PHANTOM reports with no underlying EFT; download Excel button |
| **Rule Findings** | All FINTRAC rule violations for the selected run, filterable by severity and rule code |
| **Reperformance** | Independent recalculation results vs reported values (Phase 2 output) |
| **Audit Log** | Append-only pipeline event log with severity filter |

The **"Upload & Run Analysis"** button opens a modal with two drag-and-drop file zones (EFT CSV + EFTR CSV), an operator ID field, and a pipeline progress timeline. On submit it calls `POST /runs/upload` (multipart form), which runs the full pipeline synchronously and returns when complete.

---

## Key API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/runs/upload` | Upload EFT + reported CSVs, run pipeline |
| `GET` | `/runs` | List all runs |
| `GET` | `/runs/{run_id}` | Run detail + summary counts |
| `GET` | `/runs/{run_id}/reconciliation` | Paginated reconciliation results |
| `GET` | `/runs/{run_id}/findings` | Rule findings (filter by severity) |
| `GET` | `/runs/{run_id}/reperformance` | Reperformance variance results |
| `GET` | `/runs/{run_id}/audit` | Audit log entries |
| `GET` | `/reports/{run_id}/missed-transactions` | Download Excel report |

Full interactive docs: `http://localhost:8000/docs`

---

## What Still Needs To Be Done

1. **Fix Render build failure** — Check build logs in Render dashboard and fix the failing pip install. The frontend is already pointing at `https://eftr-api.onrender.com`.

2. **Phase 2 reperformance** — The reperformance engine (`src/eftr/reperformance/`) and Bank of Canada FX client (`src/eftr/fx/boc_client.py`) are built. Run via:
   ```bash
   python scripts/run_phase2.py --run-id <run_id>
   ```

3. **Persistent database on Render** — The free tier uses an ephemeral filesystem; data is lost on redeploy. For persistence, add a Render PostgreSQL database (free tier available) and set `DATABASE_URL` to the Postgres connection string in Render environment variables.

4. **Delete the broken Vercel backend project** — `eft-reporting-7u7e` in Vercel was a failed attempt to host FastAPI as a serverless function (Python bundle too large). It can be deleted from the Vercel dashboard.

---

## Credentials

API tokens for Vercel and Render were used during setup and should be rotated.

- **Vercel:** vercel.com → Settings → Tokens → delete the `cli-deploy` token and create a new one
- **Render:** dashboard.render.com → Account Settings → API Keys → revoke and regenerate
