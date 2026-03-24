# Vercel Python entrypoint.
# app must be defined unconditionally at module level for Vercel's FastAPI detection.
import traceback as _tb

from fastapi import FastAPI

app = FastAPI(title="EFTR API")
_startup_error = None


@app.get("/health")
def _health():
    if _startup_error:
        return {"status": "startup_error", "error": _startup_error[0], "traceback": _startup_error[1]}
    return {"status": "ok"}


# Now try to load the real app — replaces the placeholder above if successful.
try:
    from src.eftr.api.main import app  # noqa: F811
    _startup_error = None
except Exception as _e:
    _startup_error = (str(_e), _tb.format_exc())
