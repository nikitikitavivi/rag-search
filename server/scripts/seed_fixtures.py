"""Seed clients directly into the database (no HTTP).

Set DATABASE_URL in .env (or export) to target the desired database, then run:

    DATABASE_URL="postgresql+asyncpg://..." python scripts/seed_fixtures.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.fixtures import _seed_clients  # noqa: E402

asyncio.run(_seed_clients())
