# Vercel Python entrypoint.
# Vercel scans standard locations (api/index.py, main.py, etc.) for the FastAPI app.
# Our app lives at src/eftr/api/main.py, so we re-export it here.
# Vercel executes with CWD = repo root, so the src.eftr import resolves correctly.
from src.eftr.api.main import app  # noqa: F401
