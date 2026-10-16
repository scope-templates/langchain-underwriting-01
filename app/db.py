import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

FACT_FIELDS = (
    "years_in_business",
    "owner",
    "locations",
    "headcount",
    "operations",
    "building",
    "parent_company",
    "recent_change",
)
SUBMISSION_STATUSES = ("open", "referred", "quoted", "declined", "bound", "not_taken")
POLICY_STATUSES = ("pending", "in_force", "expired", "cancelled", "non_renewed")
BROKERAGE_STATUSES = ("active", "inactive")
CLAIM_KINDS = ("slip_and_fall", "kitchen_fire", "liquor_liability", "spoilage", "theft")
CLAIM_STATUSES = ("open", "closed")
CONTACT_KINDS = ("inspection", "broker_call")
CARRIERS = ("Callander Indemnity Company", "Coteau Casualty Company")
WRITTEN_STATES = ("IA", "IL", "KS", "MN", "MO", "NE", "SD", "WI")
PREMIUM_AUTHORITY = 20_000
VALUE_AUTHORITY = 5_000_000
STATUS_MISMATCH = "a decision entry must match the submission status"
EARLIEST_DATE, LAST_DATE = "1990-01-01", "2040-12-31"
HISTORY_TABLES = ("brokerages", "submissions", "inspections_and_calls", "facts", "notes", "claims")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _day(column: str, nullable: bool = False) -> str:
    check = f"date({column}, '+0 days') IS {column} AND {column} BETWEEN '{EARLIEST_DATE}' AND '{LAST_DATE}'"
    return f"CHECK ({column} IS NULL OR ({check}))" if nullable else f"CHECK ({check})"


def _moment(column: str) -> str:
    return (f"CHECK (datetime({column}, '+0 seconds') IS replace({column}, 'T', ' ') "
            f"AND {column} BETWEEN '{EARLIEST_DATE}' AND '{LAST_DATE}T23:59:59')")


def _filled(column: str) -> str:
    return f"CHECK (length(trim({column})) > 0)"


def _no_replace(table: str, label: str) -> str:
    return f"""
CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table}
WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id)
BEGIN
    SELECT RAISE(ABORT, '{label}');
END;
"""


def _unchangeable(table: str, label: str) -> str:
    return f"""
CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table}
BEGIN
    SELECT RAISE(ABORT, '{label}');
END;

CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table}
BEGIN
    SELECT RAISE(ABORT, '{label}');
END;
"""


def _append_only(table: str) -> str:
    return _unchangeable(table, f"{table} are append-only") + _no_replace(table, f"{table} are append-only")


def _changed(columns: tuple[str, ...]) -> str:
    return " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in columns)


def _claim_in_term(event: str) -> str:
    return f"""
CREATE TRIGGER IF NOT EXISTS claims_in_term_{event.split()[0].lower()} BEFORE {event} ON claims
WHEN NOT EXISTS (
    SELECT 1 FROM policies p WHERE p.id = NEW.policy_id
      AND NEW.date_of_loss >= p.effective AND NEW.date_of_loss < p.expires
      AND (p.cancelled_on IS NULL OR NEW.date_of_loss < p.cancelled_on)
)
BEGIN
    SELECT RAISE(ABORT, 'a claim''s date of loss falls inside its policy''s term');
END;
"""


def _policies_table(name: str, statuses: tuple[str, ...]) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {name} (
    id INTEGER PRIMARY KEY,
    insured TEXT NOT NULL {_filled("insured")},
    state TEXT NOT NULL CHECK (state IN ({_quoted(WRITTEN_STATES)})),
    carrier TEXT NOT NULL CHECK (carrier IN ({_quoted(CARRIERS)})),
    brokerage_id INTEGER NOT NULL REFERENCES brokerages(id),
    effective TEXT NOT NULL {_day("effective")},
    expires TEXT NOT NULL {_day("expires")},
    annual_premium INTEGER NOT NULL CHECK (annual_premium > 0),
    limits TEXT NOT NULL {_filled("limits")},
    status TEXT NOT NULL CHECK (status IN ({_quoted(statuses)})),
    cancelled_on TEXT {_day("cancelled_on", nullable=True)},
    prior_policy_id INTEGER REFERENCES policies(id),
    submission_id INTEGER REFERENCES submissions(id) DEFERRABLE INITIALLY DEFERRED,
    CHECK (expires > effective),
    CHECK ((status = 'cancelled') = (cancelled_on IS NOT NULL)),
    CHECK (cancelled_on IS NULL OR (cancelled_on >= effective AND cancelled_on < expires))
);
"""


POLICY_TERMS = ("insured", "state", "carrier", "brokerage_id", "effective", "expires", "annual_premium", "limits",
                "prior_policy_id", "submission_id")


def _policy_rules() -> str:
    return f"""{_no_replace("policies", "policies rows cannot be replaced")}
CREATE TRIGGER IF NOT EXISTS policies_keep_their_terms
BEFORE UPDATE OF {", ".join(POLICY_TERMS)} ON policies
WHEN {_changed(POLICY_TERMS)}
BEGIN
    SELECT RAISE(ABORT, 'a written policy keeps its terms');
END;

CREATE TRIGGER IF NOT EXISTS renewal_terms_follow_on BEFORE INSERT ON policies
WHEN NEW.prior_policy_id IS NOT NULL
  AND NEW.effective IS NOT (SELECT expires FROM policies WHERE id = NEW.prior_policy_id)
BEGIN
    SELECT RAISE(ABORT, 'a renewal term starts the day the prior term expires');
END;
"""


LAST_DECISION = "(SELECT max(id) FROM decisions WHERE submission_id = NEW.id)"
QUOTE_COLUMNS = "annual_premium, deductible, terms, decided_by, decided_on"
WITHIN_AUTHORITY = f"d.premium <= {PREMIUM_AUTHORITY} AND NEW.total_insured_value <= {VALUE_AUTHORITY}"

DESK = f"""
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL {_filled("name")},
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('underwriter', 'senior', 'viewer'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    created_at TEXT NOT NULL {_moment("created_at")}
);

CREATE TABLE IF NOT EXISTS brokerages (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL {_filled("name")},
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    appointed_on TEXT NOT NULL {_day("appointed_on")},
    status TEXT NOT NULL CHECK (status IN ({_quoted(BROKERAGE_STATUSES)}))
);

{_policies_table("policies", POLICY_STATUSES[1:])}
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY,
    business TEXT NOT NULL {_filled("business")},
    dba TEXT,
    state TEXT NOT NULL CHECK (state IN ({_quoted(WRITTEN_STATES)})),
    address TEXT NOT NULL {_filled("address")},
    class_of_business TEXT NOT NULL {_filled("class_of_business")},
    requested_limits TEXT NOT NULL {_filled("requested_limits")},
    total_insured_value INTEGER NOT NULL CHECK (total_insured_value > 0),
    brokerage_id INTEGER NOT NULL REFERENCES brokerages(id),
    broker_contact TEXT NOT NULL {_filled("broker_contact")},
    received_on TEXT NOT NULL {_day("received_on")},
    entered_by INTEGER NOT NULL REFERENCES staff(id),
    renewal_of INTEGER REFERENCES policies(id),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ({_quoted(SUBMISSION_STATUSES)})),
    decided_by INTEGER REFERENCES staff(id),
    decided_on TEXT {_day("decided_on", nullable=True)},
    annual_premium INTEGER,
    deductible INTEGER,
    terms TEXT
);

CREATE TABLE IF NOT EXISTS inspections_and_calls (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    kind TEXT NOT NULL CHECK (kind IN ({_quoted(CONTACT_KINDS)})),
    with_whom TEXT NOT NULL {_filled("with_whom")},
    held_on TEXT NOT NULL {_day("held_on")},
    recorded_by INTEGER NOT NULL REFERENCES staff(id),
    findings TEXT NOT NULL {_filled("findings")}
);

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    field TEXT NOT NULL CHECK (field IN ({_quoted(FACT_FIELDS)})),
    value TEXT NOT NULL {_filled("value")},
    checked_on TEXT NOT NULL {_day("checked_on")},
    checked_by INTEGER NOT NULL REFERENCES staff(id),
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    author INTEGER NOT NULL REFERENCES staff(id),
    written_at TEXT NOT NULL {_moment("written_at")},
    body TEXT NOT NULL {_filled("body")}
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY,
    actor INTEGER NOT NULL REFERENCES staff(id),
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    action TEXT NOT NULL CHECK (action IN ('quote', 'decline', 'confirm', 'bind', 'not_taken')),
    premium INTEGER,
    deductible INTEGER,
    terms TEXT,
    at TEXT NOT NULL {_moment("at")},
    CHECK (action <> 'quote' OR (coalesce(premium, 0) > 0 AND coalesce(deductible, 0) > 0))
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES policies(id),
    date_of_loss TEXT NOT NULL {_day("date_of_loss")},
    reported_on TEXT NOT NULL {_day("reported_on")},
    kind TEXT NOT NULL CHECK (kind IN ({_quoted(CLAIM_KINDS)})),
    paid INTEGER NOT NULL CHECK (paid >= 0),
    reserve INTEGER NOT NULL CHECK (reserve >= 0),
    status TEXT NOT NULL CHECK (status IN ({_quoted(CLAIM_STATUSES)})),
    CHECK (reported_on >= date_of_loss),
    CHECK (status = 'open' OR reserve = 0)
);
{_append_only("decisions")}
{"".join(_no_replace(t, f"{t} rows cannot be replaced") for t in HISTORY_TABLES)}
CREATE TRIGGER IF NOT EXISTS decisions_actor_role BEFORE INSERT ON decisions
WHEN coalesce((SELECT role FROM staff WHERE id = NEW.actor), '') NOT IN ('underwriter', 'senior')
  OR (NEW.action = 'confirm' AND (
        (SELECT role FROM staff WHERE id = NEW.actor) <> 'senior'
        OR NEW.actor = (SELECT actor FROM decisions WHERE submission_id = NEW.submission_id
                        AND action = 'quote' ORDER BY id DESC LIMIT 1)))
BEGIN
    SELECT RAISE(ABORT, 'the actor cannot take this decision');
END;

CREATE TRIGGER IF NOT EXISTS decisions_match_status BEFORE INSERT ON decisions
WHEN NOT EXISTS (
    SELECT 1 FROM submissions s WHERE s.id = NEW.submission_id AND (
        (NEW.action = 'quote' AND s.status = 'open')
        OR (NEW.action = 'decline' AND s.status IN ('open', 'referred'))
        OR (NEW.action = 'confirm' AND s.status = 'referred')
        OR (NEW.action IN ('bind', 'not_taken') AND s.status = 'quoted')
    )
)
BEGIN
    SELECT RAISE(ABORT, '{STATUS_MISMATCH}');
END;

CREATE TRIGGER IF NOT EXISTS submissions_start_open BEFORE INSERT ON submissions
WHEN NEW.status <> 'open' OR NEW.decided_by IS NOT NULL OR NEW.decided_on IS NOT NULL
  OR NEW.annual_premium IS NOT NULL OR NEW.deductible IS NOT NULL OR NEW.terms IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'a submission starts open and undecided');
END;

CREATE TRIGGER IF NOT EXISTS submissions_from_active_brokerages BEFORE INSERT ON submissions
WHEN (SELECT status FROM brokerages WHERE id = NEW.brokerage_id) IS NOT 'active'
BEGIN
    SELECT RAISE(ABORT, 'a submission comes from an active brokerage');
END;

CREATE TRIGGER IF NOT EXISTS submission_risk_is_fixed
BEFORE UPDATE OF total_insured_value, renewal_of ON submissions
WHEN NEW.total_insured_value IS NOT OLD.total_insured_value OR NEW.renewal_of IS NOT OLD.renewal_of
BEGIN
    SELECT RAISE(ABORT, 'a submission keeps its insured value and renewal link');
END;

CREATE TRIGGER IF NOT EXISTS submission_status_needs_decision
BEFORE UPDATE OF status ON submissions
WHEN NEW.status <> OLD.status AND NOT EXISTS (
    SELECT 1 FROM decisions d WHERE d.id = {LAST_DECISION} AND (
        (NEW.status = 'quoted' AND d.action = 'quote' AND OLD.status = 'open' AND {WITHIN_AUTHORITY})
        OR (NEW.status = 'referred' AND d.action = 'quote' AND OLD.status = 'open' AND NOT ({WITHIN_AUTHORITY}))
        OR (NEW.status = 'quoted' AND d.action = 'confirm' AND OLD.status = 'referred')
        OR (NEW.status = 'declined' AND d.action = 'decline' AND OLD.status IN ('open', 'referred'))
        OR (NEW.status = 'bound' AND d.action = 'bind' AND OLD.status = 'quoted')
        OR (NEW.status = 'not_taken' AND d.action = 'not_taken' AND OLD.status = 'quoted')
    )
)
BEGIN
    SELECT RAISE(ABORT, 'a status change needs a matching decision entry');
END;

CREATE TRIGGER IF NOT EXISTS decided_submissions_are_final
BEFORE UPDATE OF {QUOTE_COLUMNS} ON submissions
WHEN OLD.status IN ('quoted', 'declined', 'bound', 'not_taken')
BEGIN
    SELECT RAISE(ABORT, 'a decided submission keeps its premium, deductible, terms and decider');
END;

CREATE TRIGGER IF NOT EXISTS submission_quote_needs_decision
BEFORE UPDATE OF {QUOTE_COLUMNS} ON submissions
WHEN OLD.status IN ('open', 'referred')
  AND (NEW.annual_premium IS NOT OLD.annual_premium OR NEW.deductible IS NOT OLD.deductible
      OR NEW.terms IS NOT OLD.terms OR NEW.decided_by IS NOT OLD.decided_by OR NEW.decided_on IS NOT OLD.decided_on)
  AND NOT EXISTS (
    SELECT 1 FROM decisions d WHERE d.id = {LAST_DECISION}
      AND d.action IN ('quote', 'decline') AND d.actor = NEW.decided_by
      AND d.premium IS NEW.annual_premium AND d.deductible IS NEW.deductible AND d.terms IS NEW.terms
      AND substr(d.at, 1, 10) = NEW.decided_on
)
BEGIN
    SELECT RAISE(ABORT, 'premium, deductible, terms and decider change only with a matching decision entry');
END;

CREATE TRIGGER IF NOT EXISTS policies_leave_in_force_once
BEFORE UPDATE OF status ON policies
WHEN NEW.status IS NOT OLD.status AND OLD.status <> 'in_force'
BEGIN
    SELECT RAISE(ABORT, 'a policy that has left in_force keeps its status');
END;

{_policy_rules()}{_claim_in_term("INSERT")}
{_claim_in_term("UPDATE OF policy_id, date_of_loss")}
"""

ASSISTANT = f"""
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,
    actor INTEGER NOT NULL REFERENCES staff(id),
    action TEXT NOT NULL CHECK (action IN ('save_note', 'scope_refused')),
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    detail TEXT NOT NULL,
    at TEXT NOT NULL {_moment("at")}
);
{_append_only("activity")}
"""

ACTIVITY_SUBJECTS = {
    "submission_id": ("save_note", "scope_refused", "tool_refused", "tool_failed"),
    "policy_id": ("policy_started", "policy_ended", "policy_cancelled"),
    "claim_id": ("claim_closed",),
    "brokerage_id": ("brokerage_status",),
}
ACTIVITY_ACTIONS = tuple(action for actions in ACTIVITY_SUBJECTS.values() for action in actions)
ACTIVITY_SUBJECT_CHECKS = ",\n    ".join(f"CHECK ((action IN ({_quoted(actions)})) = ({column} IS NOT NULL))"
                                        for column, actions in ACTIVITY_SUBJECTS.items())
SUBMISSION_DETAILS = ("business", "dba", "state", "address", "class_of_business", "requested_limits", "brokerage_id",
                      "broker_contact", "received_on", "entered_by")
CLAIM_IDENTITY = ("policy_id", "date_of_loss", "reported_on", "kind")
LAST_POLICY_ENTRY = "(SELECT {} FROM activity WHERE id = (SELECT max(id) FROM activity WHERE policy_id = OLD.id))"
LAST_POLICY_ACTION = f"coalesce({LAST_POLICY_ENTRY.format('action')}, '')"
LAST_POLICY_DAY = f"coalesce({LAST_POLICY_ENTRY.format('substr(at, 1, 10)')}, '')"


def ends_non_renewed(policy_id: str) -> str:
    """SQL true when the term at `policy_id` ends with no renewal term and a renewal that was declined or not
    taken; such a term ends `non_renewed`, any other ends `expired`."""
    return (f"(NOT EXISTS (SELECT 1 FROM policies n WHERE n.prior_policy_id = {policy_id}) AND EXISTS "
            f"(SELECT 1 FROM submissions s WHERE s.renewal_of = {policy_id} "
            "AND s.status IN ('declined', 'not_taken')))")



UPKEEP = f"""
{_policies_table("policies_calendar", POLICY_STATUSES)}
INSERT INTO policies_calendar SELECT * FROM policies;
DROP TABLE policies;
ALTER TABLE policies_calendar RENAME TO policies;
{_policy_rules()}
CREATE TABLE activity_upkeep (
    id INTEGER PRIMARY KEY,
    actor INTEGER NOT NULL REFERENCES staff(id),
    action TEXT NOT NULL CHECK (action IN ({_quoted(ACTIVITY_ACTIONS)})),
    submission_id INTEGER REFERENCES submissions(id),
    policy_id INTEGER REFERENCES policies(id),
    claim_id INTEGER REFERENCES claims(id),
    brokerage_id INTEGER REFERENCES brokerages(id),
    detail TEXT NOT NULL,
    at TEXT NOT NULL {_moment("at")},
    {ACTIVITY_SUBJECT_CHECKS}
);
INSERT INTO activity_upkeep (id, actor, action, submission_id, detail, at)
    SELECT id, actor, action, submission_id, detail, at FROM activity;
DROP TABLE activity;
ALTER TABLE activity_upkeep RENAME TO activity;
{_append_only("activity")}
{"".join(_unchangeable(t, f"{t} rows are kept as written") for t in ("inspections_and_calls", "facts", "notes"))}
CREATE UNIQUE INDEX IF NOT EXISTS one_open_renewal_per_policy ON submissions (renewal_of)
WHERE renewal_of IS NOT NULL AND status IN ('open', 'referred', 'quoted');

CREATE UNIQUE INDEX IF NOT EXISTS one_renewal_term_per_policy ON policies (prior_policy_id)
WHERE prior_policy_id IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS closed_submissions_keep_their_details
BEFORE UPDATE OF {", ".join(SUBMISSION_DETAILS)} ON submissions
WHEN OLD.status IN ('declined', 'bound', 'not_taken') AND ({_changed(SUBMISSION_DETAILS)})
BEGIN
    SELECT RAISE(ABORT, 'a bound, declined or not-taken submission keeps its details');
END;

CREATE TRIGGER IF NOT EXISTS policy_status_follows_the_calendar BEFORE UPDATE OF status ON policies
WHEN NEW.status IS NOT OLD.status AND NOT (
    (OLD.status = 'pending' AND NEW.status = 'in_force'
        AND {LAST_POLICY_ACTION} = 'policy_started' AND {LAST_POLICY_DAY} >= OLD.effective)
    OR (OLD.status = 'in_force' AND {LAST_POLICY_ACTION} = 'policy_ended' AND {LAST_POLICY_DAY} >= OLD.expires
        AND NEW.status = CASE WHEN {ends_non_renewed("OLD.id")} THEN 'non_renewed' ELSE 'expired' END)
    OR (OLD.status IN ('pending', 'in_force') AND NEW.status = 'cancelled'
        AND {LAST_POLICY_ACTION} = 'policy_cancelled')
)
BEGIN
    SELECT RAISE(ABORT, 'a policy status follows its dates and needs its entry in activity');
END;

CREATE TRIGGER IF NOT EXISTS pending_policies_cancel_flat BEFORE UPDATE OF status ON policies
WHEN OLD.status = 'pending' AND NEW.status = 'cancelled' AND NEW.cancelled_on IS NOT OLD.effective
BEGIN
    SELECT RAISE(ABORT, 'a policy that has not started is cancelled flat, as of its effective date');
END;

CREATE TRIGGER IF NOT EXISTS cancellation_date_is_fixed BEFORE UPDATE OF cancelled_on ON policies
WHEN NEW.cancelled_on IS NOT OLD.cancelled_on AND OLD.status NOT IN ('pending', 'in_force')
BEGIN
    SELECT RAISE(ABORT, 'a cancellation date is set once, when the policy is cancelled');
END;

CREATE TRIGGER IF NOT EXISTS cancellation_comes_after_every_loss BEFORE UPDATE OF status, cancelled_on ON policies
WHEN NEW.cancelled_on IS NOT NULL
  AND EXISTS (SELECT 1 FROM claims c WHERE c.policy_id = OLD.id AND c.date_of_loss >= NEW.cancelled_on)
BEGIN
    SELECT RAISE(ABORT, 'a policy is cancelled only after every loss it covers');
END;

CREATE TRIGGER IF NOT EXISTS claims_move_forward BEFORE UPDATE ON claims
WHEN OLD.status = 'closed' OR NEW.paid < OLD.paid OR {_changed(CLAIM_IDENTITY)}
BEGIN
    SELECT RAISE(ABORT, 'a claim moves only forward: open to closed, paid never lowered');
END;

CREATE TRIGGER IF NOT EXISTS claims_no_delete BEFORE DELETE ON claims
BEGIN
    SELECT RAISE(ABORT, 'claims are kept');
END;

CREATE TRIGGER IF NOT EXISTS brokerage_status_needs_an_entry BEFORE UPDATE OF status ON brokerages
WHEN NEW.status IS NOT OLD.status AND NOT EXISTS (
    SELECT 1 FROM activity a WHERE a.id = (SELECT max(id) FROM activity WHERE brokerage_id = OLD.id)
      AND a.action = 'brokerage_status' AND a.detail = NEW.status
)
BEGIN
    SELECT RAISE(ABORT, 'a brokerage status change needs its entry in activity');
END;
"""

MIGRATIONS = (
    ("the underwriting desk", DESK),
    ("the assistant's activity log", ASSISTANT),
    ("policy terms that follow the calendar, cancellations, claim closing and brokerage status", UPKEEP),
)


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | Path) -> None:
    """Applies, in order and each in its own transaction, the migrations past the file's PRAGMA user_version.
    Foreign keys are off while a migration rebuilds a table, and checked once they are all applied."""
    conn = connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("PRAGMA legacy_alter_table = ON")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for number, (_, sql) in enumerate(MIGRATIONS, start=1):
            if number > version:
                conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
        broken = conn.execute("PRAGMA foreign_key_check").fetchall()
        if broken:
            raise RuntimeError(f"the store has rows whose foreign keys do not match: {[tuple(r) for r in broken]}")
    finally:
        conn.close()


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()
