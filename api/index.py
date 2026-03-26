# Vercel Python entrypoint.
# Strips the /api prefix added by vercel.json rewrites before forwarding
# to the FastAPI application, so routes like /runs/upload work unchanged.
import sys
import traceback as _tb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_startup_error = None


class _StripApiPrefix:
    """ASGI middleware: /api/runs/upload → /runs/upload."""

    def __init__(self, asgi_app):
        self._app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in ("http", "websocket"):
            path = scope.get("path", "")
            if path.startswith("/api"):
                new_path = path[4:] or "/"
                scope = dict(scope)
                scope["path"] = new_path
                scope["raw_path"] = new_path.encode("latin-1")
        await self._app(scope, receive, send)


try:
    from src.eftr.api.main import _bootstrap, app as _inner  # noqa: E402

    _bootstrap()
    app = _StripApiPrefix(_inner)
except Exception as _e:
    _startup_error = (str(_e), _tb.format_exc())
    from fastapi import FastAPI as _FastAPI  # noqa: E402

    _fallback = _FastAPI(title="EFTR API — startup error")

    @_fallback.get("/health")
    def _health():
        return {
            "status": "startup_error",
            "error": _startup_error[0],
            "detail": _startup_error[1],
        }

    app = _fallback
