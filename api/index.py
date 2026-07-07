"""Vercel serverless entry point — wraps the FastAPI app."""
import os
import sys

# api/index.py runs from /var/task/api/; app code lives at /var/task/server/
_server = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
sys.path.insert(0, _server)

from app.main import app  # noqa: E402
