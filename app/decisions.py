import sqlite3
from datetime import date, datetime, timedelta

from app.auth import Staff
from app.book import lapsed
from app.db import PREMIUM_AUTHORITY, STATUS_MISMATCH, VALUE_AUTHORITY
from app.problems import Problem

BIND_AHEAD_DAYS = 90
ACTION_FIELDS = {
    "quote": {"premium", "deductible", "terms"},
    "decline": set(),
    "confirm": {"premium", "deductible", "terms"},
    "bind": {"effective", "carrier"},
    "not_taken": set(),
}


def within_authority(premium: int, total_insured_value: int) -> bool:
    return premium <= PREMIUM_AUTHORITY and total_insured_value <= VALUE_AUTHORITY


def record(
    conn: sqlite3.Connection,
    submission: sqlite3.Row,
    actor_id: int,
    action: str,
    premium: int | None,
    deductible: int | None,
    terms: str | None,
    at: datetime,
) -> None:
    """Writes the decision entry and moves the submission on from the status it was read with; the caller owns
    the transaction."""
    sub_id, from_status = submission["id"], submission["status"]
    changed = Problem(409, "status_changed", f"Submission {sub_id} is no longer {from_status}.")
    try:
        conn.execute(
            "INSERT INTO decisions (actor, submission_id, action, premium, deductible, terms, at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (actor_id, sub_id, action, premium, deductible, terms, at.isoformat()),
        )
    except sqlite3.IntegrityError as exc:
        if STATUS_MISMATCH in str(exc):
            raise changed from exc
        raise
    if action in ("quote", "decline"):
        if action == "decline":
            status = "declined"
        else:
            status = "quoted" if within_authority(premium, submission["total_insured_value"]) else "referred"
        cur = conn.execute(
            "UPDATE submissions SET status = ?, decided_by = ?, decided_on = ?, annual_premium = ?, deductible = ?, "
            "terms = ? WHERE id = ? AND status = ?",
            (status, actor_id, at.date().isoformat(), premium, deductible, terms, sub_id, from_status),
        )
    else:
        status = {"confirm": "quoted", "bind": "bound", "not_taken": "not_taken"}[action]
        cur = conn.execute(
            "UPDATE submissions SET status = ? WHERE id = ? AND status = ?", (status, sub_id, from_status)
        )
    if cur.rowcount == 0:
        raise changed


def decide(
    conn: sqlite3.Connection,
    submission: sqlite3.Row,
    staff: Staff,
    action: str,
    fields: dict,
    now: datetime,
) -> None:
    """Checks one decision and records it, opening a policy on a bind. The policy a renewal follows keeps its
    status until its term ends."""
    sub_id, status = submission["id"], submission["status"]
    unused = sorted(key for key, value in fields.items() if value is not None and key not in ACTION_FIELDS[action])
    if unused:
        raise Problem(422, "field_not_used", f"{action} does not take {', '.join(unused)}.")
    renewing = None
    if submission["renewal_of"] is not None:
        renewing = conn.execute("SELECT * FROM policies WHERE id = ?", (submission["renewal_of"],)).fetchone()
    premium, deductible, terms = submission["annual_premium"], submission["deductible"], submission["terms"]
    if action == "quote":
        if status != "open":
            raise Problem(409, "submission_decided", f"Submission {sub_id} is {status}.")
        premium, deductible, terms = fields.get("premium"), fields.get("deductible"), fields.get("terms")
        if premium is None or deductible is None:
            raise Problem(422, "quote_incomplete", "A quote needs an annual premium and a deductible in dollars.")
    elif action == "decline":
        if status not in ("open", "referred"):
            raise Problem(409, "submission_decided", f"Submission {sub_id} is already {status}.")
        premium = deductible = terms = None
    elif action == "confirm":
        _check_confirm(conn, submission, staff, fields)
    elif status != "quoted":
        raise Problem(409, "not_quoted", f"Submission {sub_id} is {status}.")
    elif action == "bind":
        if renewing is not None and renewing["status"] != "in_force":
            raise Problem(409, "policy_lapsed" if lapsed(conn, renewing) else "policy_not_in_force",
                          f"Policy {renewing['id']} is {renewing['status']}; a renewal binds only while the "
                          "expiring term is in force.")
        effective, carrier = _bind_terms(renewing, fields, now.date())
    with conn:
        record(conn, submission, staff.id, action, premium, deductible, terms, now)
        if action == "bind":
            _open_policy(conn, submission, renewing, effective, carrier, now.date())


def _check_confirm(conn: sqlite3.Connection, submission: sqlite3.Row, staff: Staff, fields: dict) -> None:
    sub_id = submission["id"]
    if staff.role != "senior":
        raise Problem(403, "role_refused", "A referred quote is confirmed by a senior underwriter.")
    if submission["status"] != "referred":
        raise Problem(409, "not_referred", f"Submission {sub_id} is {submission['status']}.")
    for key, column in (("premium", "annual_premium"), ("deductible", "deductible"), ("terms", "terms")):
        if fields.get(key) not in (None, submission[column]):
            raise Problem(422, "confirm_changes_quote", "Confirming keeps the premium, deductible and terms quoted.")
    quoter = conn.execute(
        "SELECT actor FROM decisions WHERE submission_id = ? AND action = 'quote' ORDER BY id DESC LIMIT 1",
        (sub_id,),
    ).fetchone()["actor"]
    if quoter == staff.id:
        raise Problem(403, "senior_is_quoter", "The person who quoted this cannot also confirm it.")


def _bind_terms(renewing: sqlite3.Row | None, fields: dict, today: date) -> tuple[date, str]:
    carrier, effective = fields.get("carrier"), fields.get("effective")
    if renewing is not None:
        term_start = date.fromisoformat(renewing["expires"])
        if effective not in (None, term_start):
            raise Problem(422, "renewal_effective_fixed",
                          f"A renewal takes effect the day policy {renewing['id']} expires ({term_start.isoformat()}).")
        effective, carrier = term_start, carrier or renewing["carrier"]
    else:
        if effective is None or carrier is None:
            raise Problem(422, "bind_incomplete", "Binding new business needs an effective date and a carrier.")
        if not today <= effective <= today + timedelta(days=BIND_AHEAD_DAYS):
            raise Problem(422, "effective_out_of_range",
                          f"The effective date must fall between today and {BIND_AHEAD_DAYS} days from today.")
    return effective, carrier


def _open_policy(conn: sqlite3.Connection, submission: sqlite3.Row, renewing: sqlite3.Row | None, effective: date,
                 carrier: str, today: date) -> None:
    """Writes the bound policy, `pending` until its effective date and `in_force` from then."""
    conn.execute(
        "INSERT INTO policies (insured, state, carrier, brokerage_id, effective, expires, annual_premium, limits, "
        "status, prior_policy_id, submission_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (submission["business"], submission["state"], carrier, submission["brokerage_id"], effective.isoformat(),
         _a_year_on(effective).isoformat(), submission["annual_premium"], submission["requested_limits"],
         "pending" if effective > today else "in_force", renewing["id"] if renewing is not None else None,
         submission["id"]),
    )


def _a_year_on(day: date) -> date:
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return day.replace(year=day.year + 1, day=28)
