import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.db import connect
from app.decisions import record

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "seed.json"
ROW_TABLES = ("staff", "brokerages", "policies", "submissions", "inspections_and_calls", "facts", "notes", "claims",
              "activity")


def rows_of(seed: dict, table: str) -> list[dict]:
    """The rows of one seed table, which holds {"columns": [...], "rows": [[...], ...]}."""
    block = seed.get(table) or {"columns": [], "rows": []}
    return [dict(zip(block["columns"], row)) for row in block["rows"]]


def load(conn: sqlite3.Connection, seed: dict) -> None:
    """Inserts the seed rows, then replays its decisions in order through the same step the decide route uses."""
    with conn:
        for table in ROW_TABLES:
            block = seed.get(table)
            if not block or not block["rows"]:
                continue
            columns = block["columns"]
            conn.executemany(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                block["rows"],
            )
        for d in rows_of(seed, "decisions"):
            submission = conn.execute("SELECT * FROM submissions WHERE id = ?", (d["submission_id"],)).fetchone()
            record(conn, submission, d["actor"], d["action"], d["premium"], d["deductible"], d["terms"],
                   datetime.fromisoformat(d["at"]))


def ensure_seeded(path: str | Path) -> None:
    conn = connect(path)
    try:
        if conn.execute("SELECT count(*) FROM staff").fetchone()[0] == 0:
            load(conn, json.loads(SEED_FILE.read_text(encoding="utf-8")))
    finally:
        conn.close()
