"""Debug endpoint to verify Vercel Python path resolution."""
import json
import os
import sys


def app(environ, start_response):
    _dir = os.path.join(os.path.dirname(__file__), "..", "server")
    body = json.dumps({
        "cwd": os.getcwd(),
        "dirname": os.path.dirname(__file__),
        "resolved": os.path.abspath(_dir),
        "server_exists": os.path.isdir(os.path.abspath(_dir)),
        "path": sys.path[:10],
    })
    start_response("200 OK", [("Content-Type", "application/json")])
    return [body.encode()]
