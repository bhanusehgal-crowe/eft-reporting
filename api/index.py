# Vercel Python entrypoint — wraps the FastAPI app at src/eftr/api/main.py
import traceback as _tb

_import_error = None
_import_tb = None

try:
    from src.eftr.api.main import app  # noqa: F401
except Exception as _e:
    _import_error = str(_e)
    _import_tb = _tb.format_exc()

    from fastapi import FastAPI

    app = FastAPI(title="EFTR API (startup failed)")

    @app.get("/health")
    def health():  # noqa: F811
        return {"status": "startup_error", "error": _import_error, "traceback": _import_tb}

    @app.get("/{path:path}")
    def catch_all(path: str):
        return {"status": "startup_error", "error": _import_error}
