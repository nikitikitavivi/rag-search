"""Cursor encoding/decoding for keyset pagination.

Cursors are opaque base64-encoded strings containing the sort key (created_at)
and the row id. We use (created_at, id) as a composite keyset so pagination is
stable even when multiple rows share the same created_at.
"""
import base64
import json
from datetime import datetime

from app.api.errors import bad_request


def encode_cursor(created_at: datetime, row_id: str) -> str:
    payload = json.dumps({"ts": created_at.isoformat(), "id": row_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return datetime.fromisoformat(payload["ts"]), payload["id"]
    except Exception as exc:
        raise bad_request("INVALID_CURSOR", "Invalid or expired cursor") from exc
