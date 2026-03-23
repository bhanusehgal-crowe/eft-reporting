"""
Vercel Python serverless entry point.
Bootstrap runs at cold-start (module import); lifespan is disabled
so Mangum does not attempt async context management.
"""
import sys
import traceback

# Ensure the repo root is on sys.path regardless of Vercel's working dir
from pathlib import Path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

_startup_error: str | None = None

try:
    from mangum import Mangum
    from src.eftr.api.main import app, _bootstrap
    _bootstrap()
except Exception:
    _startup_error = traceback.format_exc()
    # Still import app so we can return a meaningful error response
    try:
        from mangum import Mangum
        from src.eftr.api.main import app
    except Exception:
        from fastapi import FastAPI
        from mangum import Mangum
        app = FastAPI()

        @app.get("/{path:path}")
        def _fallback(path: str):
            return {"error": "startup_failed", "detail": _startup_error}


if _startup_error:
    from fastapi import FastAPI as _FA
    _err = _startup_error

    @app.get("/health")
    def _health_err():
        return {"status": "error", "detail": _err}

handler = Mangum(app, lifespan="off")
