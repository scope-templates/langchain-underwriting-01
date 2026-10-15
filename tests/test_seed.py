import importlib.util
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from app.db import POLICY_STATUSES, SUBMISSION_STATUSES, connect, init_db
from app.seed import SEED_FILE, ensure_seeded, load, rows_of

ROOT = Path(__file__).resolve().parent.parent
AS_OF, LOG_BEGAN = "2026-10-01", "2026-04-01"
TABLES = ("staff", "brokerages", "policies", "submissions", "inspections_and_calls", "facts", "notes", "decisions",
          "claims", "activity")


def load_generator():
    spec = importlib.util.spec_from_file_location("make_seed", ROOT / "scripts" / "make_seed.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def seed() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def test_generator_reproduces_the_committed_seed_bytes():
    assert load_generator().build().encode("utf-8") == SEED_FILE.read_bytes()


def test_seed_loads_every_row(db):
    data = seed()
    for table in TABLES:
        assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == len(rows_of(data, table)), table
    per_submission = Counter(r[0] for r in db.execute("SELECT submission_id FROM facts"))
    assert len(per_submission) == len(rows_of(data, "submissions"))
    assert min(per_submission.values()) >= 2 and max(per_submission.values()) <= 5


def test_seed_holds_every_status(db):
    assert {r[0] for r in db.execute("SELECT DISTINCT status FROM submissions")} == set(SUBMISSION_STATUSES)
    assert {r[0] for r in db.execute("SELECT DISTINCT status FROM policies")} == set(POLICY_STATUSES)


def test_seed_decisions_replay_into_submission_status(db):
    expected = {"open": [[]], "referred": [["quote"]], "quoted": [["quote"], ["quote", "confirm"]],
                "declined": [["decline"], ["quote", "decline"]],
                "bound": [["quote", "bind"], ["quote", "confirm", "bind"]],
                "not_taken": [["quote", "not_taken"], ["quote", "confirm", "not_taken"]]}
    for sub_id, status in db.execute("SELECT id, status FROM submissions"):
        actions = [r[0] for r in db.execute(
            "SELECT action FROM decisions WHERE submission_id = ? ORDER BY id", (sub_id,))]
        assert actions in expected[status], (sub_id, status, actions)


def test_seed_policy_statuses_follow_their_dates_on_the_first_of_october(db):
    for status, effective, expires, renewal in db.execute(
            "SELECT p.status, p.effective, p.expires, (SELECT group_concat(s.status) FROM submissions s "
            "WHERE s.renewal_of = p.id) FROM policies p WHERE p.status <> 'cancelled'"):
        if effective > AS_OF:
            assert status == "pending"
        elif expires > AS_OF:
            assert status == "in_force"
        elif renewal == "bound":
            assert status == "expired"
        elif renewal in ("declined", "not_taken"):
            assert status == "non_renewed"
        else:
            assert status in ("expired", "non_renewed")


def test_seed_renewal_terms_start_when_the_expiring_term_ends(db):
    for status, effective_matches in db.execute(
            "SELECT s.status, n.effective = p.expires FROM submissions s "
            "JOIN policies p ON p.id = s.renewal_of LEFT JOIN policies n ON n.submission_id = s.id"):
        assert effective_matches == (1 if status == "bound" else None)


def test_seed_renewals_bind_while_the_expiring_term_is_in_force(db):
    late = db.execute("SELECT count(*) FROM submissions s JOIN policies p ON p.id = s.renewal_of "
                      "JOIN decisions d ON d.submission_id = s.id AND d.action = 'bind' "
                      "WHERE substr(d.at, 1, 10) >= p.expires").fetchone()[0]
    assert late == 0


def test_seed_activity_holds_each_step_taken_since_the_log_began(db):
    missing = {
        "cancellation": "SELECT count(*) FROM policies p WHERE status = 'cancelled' AND cancelled_on >= ? "
                        "AND NOT EXISTS (SELECT 1 FROM activity a WHERE a.policy_id = p.id "
                        "AND a.action = 'policy_cancelled' AND substr(a.at, 1, 10) >= p.cancelled_on)",
        "term ended": "SELECT count(*) FROM policies p WHERE status IN ('expired', 'non_renewed') AND expires >= ? "
                      "AND NOT EXISTS (SELECT 1 FROM activity a WHERE a.policy_id = p.id "
                      "AND a.action = 'policy_ended' AND substr(a.at, 1, 10) >= p.expires)",
        "term started early": "SELECT count(*) FROM activity a JOIN policies p ON p.id = a.policy_id "
                              "WHERE a.action = 'policy_started' AND substr(a.at, 1, 10) < max(p.effective, ?)",
        "claim closed": "SELECT count(*) FROM activity a JOIN claims c ON c.id = a.claim_id "
                        "WHERE c.status <> 'closed' AND a.at >= ?",
    }
    for what, sql in missing.items():
        assert db.execute(sql, (LOG_BEGAN,)).fetchone()[0] == 0, what
    assert db.execute("SELECT min(at) >= ? AND max(at) < ? FROM activity", (LOG_BEGAN, f"{AS_OF}T10:00")
                      ).fetchone()[0] == 1


def test_seed_dates_are_in_order(db):
    for table, column in (("inspections_and_calls", "held_on"), ("notes", "substr(written_at, 1, 10)"),
                          ("decisions", "substr(at, 1, 10)")):
        early = db.execute(f"SELECT count(*) FROM {table} t JOIN submissions s ON s.id = t.submission_id "
                           f"WHERE {column} < s.received_on OR {column} > '2026-09-30'").fetchone()[0]
        assert early == 0, table
    assert db.execute("SELECT min(checked_on) >= '2025-06-01' AND max(checked_on) <= '2026-09-30' "
                      "FROM facts").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM claims WHERE reported_on > '2026-09-30'").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM policies WHERE status IN ('pending', 'in_force') AND expires <= ?",
                      (AS_OF,)).fetchone()[0] == 0


def test_seed_desk_work_falls_on_weekdays(db):
    days = [r[0] for table, column in (("inspections_and_calls", "held_on"), ("facts", "checked_on"),
                                       ("notes", "written_at"), ("decisions", "at"), ("submissions", "received_on"),
                                       ("claims", "reported_on"), ("brokerages", "appointed_on"), ("activity", "at"))
            for r in db.execute(f"SELECT substr({column}, 1, 10) FROM {table}")]
    assert all(date.fromisoformat(d).weekday() < 5 for d in days)


def test_seed_loads_once(db_path):
    ensure_seeded(db_path)
    conn = connect(db_path)
    assert conn.execute("SELECT count(*) FROM submissions").fetchone()[0] == len(rows_of(seed(), "submissions"))
    conn.close()


def test_seed_load_takes_empty_tables(tmp_path):
    path = tmp_path / "small.db"
    init_db(path)
    data = seed()
    conn = connect(path)
    load(conn, {"staff": data["staff"], "notes": {"columns": ["id"], "rows": []}})
    assert conn.execute("SELECT count(*) FROM staff").fetchone()[0] == len(rows_of(data, "staff"))
    conn.close()


def test_seed_businesses_do_not_share_names(db):
    owners = {}
    for business, dba in db.execute("SELECT DISTINCT business, dba FROM submissions"):
        assert owners.setdefault(dba, business) == business, dba
    names = [r[0] for r in db.execute("SELECT business FROM submissions UNION SELECT insured FROM policies")]
    initials = [name.split()[0] for name in names]
    assert len(set(initials)) == len(initials)
