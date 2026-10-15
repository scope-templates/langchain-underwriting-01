import sqlite3
from datetime import datetime

from app.db import ACTIVITY_SUBJECTS


def log(conn: sqlite3.Connection, actor_id: int, action: str, detail: str, at: datetime, **subject: int) -> None:
    """Appends an activity entry about one subject, given as submission_id, policy_id, claim_id or brokerage_id;
    the caller owns the transaction."""
    (column, subject_id), = subject.items()
    if column not in ACTIVITY_SUBJECTS:
        raise ValueError(f"activity has no subject column {column}")
    conn.execute(
        f"INSERT INTO activity (actor, action, {column}, detail, at) VALUES (?, ?, ?, ?, ?)",
        (actor_id, action, subject_id, detail, at.isoformat()),
    )
