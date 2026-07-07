"""Vercel serverless entry point — wraps the FastAPI app."""
import os
import sys
import json

_dir = os.path.join(os.path.dirname(__file__), "..", "server")
_abs = os.path.abspath(_dir)
sys.path.insert(0, _abs)

# Print diagnostics to stderr so they appear in Vercel runtime logs
print(json.dumps({
    "file": __file__,
    "cwd": os.getcwd(),
    "resolved": _abs,
    "path": sys.path[:5],
}), file=sys.stderr)

from app.main import app  # noqa: E402
