"""Vercel serverless entry point — wraps the FastAPI app."""
import importlib
import os
import sys

_server = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
sys.path.insert(0, _server)

app = importlib.import_module("app.main").app
