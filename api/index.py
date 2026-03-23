"""
Vercel Python serverless entry point.
Wraps the FastAPI app with Mangum so Vercel can invoke it.
"""
from mangum import Mangum
from src.eftr.api.main import app  # noqa: F401 – triggers lifespan bootstrap

handler = Mangum(app, lifespan="auto")
