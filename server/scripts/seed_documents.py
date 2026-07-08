"""Seed test documents directly into the database (no HTTP).

Set DATABASE_URL and optionally OPENAI_API_KEY / OPENAI_EMBEDDINGS_API_KEY
in .env (or export), then run:

    DATABASE_URL="postgresql+asyncpg://..." python scripts/seed_documents.py

Requires the "test@metadata.com" client to exist.  If it does not,
the script creates it automatically.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.fixtures import _seed_documents  # noqa: E402

asyncio.run(_seed_documents())
