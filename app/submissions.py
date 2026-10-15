import sqlite3
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth import UNDERWRITING, Staff, signed_in, underwriting_staff
from app.book import bring_book_to_date, lapsed, renewal_term
from app.db import CARRIERS, CONTACT_KINDS, FACT_FIELDS, SUBMISSION_STATUSES, WRITTEN_STATES, get_db
from app.decisions import decide
from app.fields import MAX_ID, Day, Deductible, InsuredValue, NoteText, Premium, RecordId, not_after_today, text
from app.problems import Problem

router = APIRouter(prefix="/submissions")


class NewSubmission(BaseModel):
    business: text(200)
    dba: text(200) | None = None
    state: Literal[WRITTEN_STATES]
    address: text(300)
    class_of_business: text(80)
    requested_limits: text(200)
    total_insured_value: InsuredValue
    brokerage_id: int = Field(ge=1, le=MAX_ID)
    broker_contact: text(200)
    received_on: Day | None = None
    renewal_of: int | None = Field(default=None, ge=1, le=MAX_ID)


class NewContact(BaseModel):
    kind: Literal[CONTACT_KINDS]
    with_whom: text(200)
    held_on: Day
    findings: NoteText


class NewFact(BaseModel):
    field: Literal[FACT_FIELDS]
    value: text(500)
    checked_on: Day
    note: text(1000) | None = None


class NewNote(BaseModel):
    body: NoteText


class Decision(BaseModel):
    action: Literal["quote", "decline", "confirm", "bind", "not_taken"]
    premium: Premium | None = None
    deductible: Deductible | None = None
    terms: text(500) | None = None
    effective: Day | None = None
    carrier: Literal[CARRIERS] | None = None


def get_submission(conn: sqlite3.Connection, submission_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()
    if row is None:
        raise Problem(404, "not_found", f"There is no submission {submission_id}.")
    return row


def submission_summary(conn: sqlite3.Connection, submission_id: int) -> dict:
    get_submission(conn, submission_id)
    row = conn.execute(
        "SELECT s.*, b.name AS brokerage, e.name AS entered_by_name, d.name AS decided_by_name "
        "FROM submissions s JOIN brokerages b ON b.id = s.brokerage_id JOIN staff e ON e.id = s.entered_by "
        "LEFT JOIN staff d ON d.id = s.decided_by WHERE s.id = ?",
        (submission_id,),
    ).fetchone()
    summary = dict(row)
    bound = conn.execute("SELECT id FROM policies WHERE submission_id = ?", (submission_id,)).fetchone()
    summary["policy_id"] = bound["id"] if bound else None
    summary["notes"] = [
        dict(n)
        for n in conn.execute(
            "SELECT n.id, n.written_at, s.name AS author, n.body FROM notes n "
            "JOIN staff s ON s.id = n.author WHERE n.submission_id = ? ORDER BY n.written_at, n.id",
            (submission_id,),
        )
    ]
    summary["decisions"] = [
        dict(d)
        for d in conn.execute(
            "SELECT d.id, d.action, d.premium, d.deductible, d.terms, d.at, s.name AS actor FROM decisions d "
            "JOIN staff s ON s.id = d.actor WHERE d.submission_id = ? ORDER BY d.id",
            (submission_id,),
        )
    ]
    return summary


def list_contacts(conn: sqlite3.Connection, submission_id: int) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT c.id, c.kind, c.with_whom, c.held_on, s.name AS recorded_by, c.findings "
            "FROM inspections_and_calls c JOIN staff s ON s.id = c.recorded_by "
            "WHERE c.submission_id = ? ORDER BY c.held_on, c.id",
            (submission_id,),
        )
    ]


def list_facts(conn: sqlite3.Connection, submission_id: int) -> list[dict]:
    return [
        dict(f)
        for f in conn.execute(
            "SELECT f.id, f.field, f.value, f.checked_on, s.name AS checked_by, f.note "
            "FROM facts f JOIN staff s ON s.id = f.checked_by "
            "WHERE f.submission_id = ? ORDER BY f.checked_on, f.id",
            (submission_id,),
        )
    ]


def insert_note(conn: sqlite3.Connection, submission_id: int, author: Staff, body: str, now: datetime) -> dict:
    """Inserts a note; the caller owns the transaction."""
    written_at = now.isoformat()
    cur = conn.execute(
        "INSERT INTO notes (submission_id, author, written_at, body) VALUES (?, ?, ?, ?)",
        (submission_id, author.id, written_at, body),
    )
    return {"id": cur.lastrowid, "submission_id": submission_id, "author": author.name,
            "written_at": written_at, "body": body}


@router.get("")
def index(
    status: Literal[SUBMISSION_STATUSES] | None = None,
    staff: Staff = Depends(signed_in),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    sql = ("SELECT s.id, s.business, s.dba, s.state, s.class_of_business, s.total_insured_value, "
           "b.name AS brokerage, s.received_on, s.renewal_of, s.status "
           "FROM submissions s JOIN brokerages b ON b.id = s.brokerage_id")
    args: tuple = ()
    if status is not None:
        sql += " WHERE s.status = ?"
        args = (status,)
    return [dict(r) for r in conn.execute(sql + " ORDER BY s.received_on DESC, s.id DESC", args)]


@router.post("", status_code=201)
def create(
    body: NewSubmission,
    request: Request,
    staff: Staff = Depends(underwriting_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    now = request.app.state.clock()
    received_on = not_after_today(body.received_on or now.date(), now.date(), "received_on")
    brokerage = conn.execute("SELECT status FROM brokerages WHERE id = ?", (body.brokerage_id,)).fetchone()
    if brokerage is None:
        raise Problem(422, "unknown_brokerage", f"There is no brokerage {body.brokerage_id}.")
    if brokerage["status"] != "active":
        raise Problem(422, "brokerage_inactive", f"Brokerage {body.brokerage_id} is {brokerage['status']}.")
    if body.renewal_of is not None:
        _check_renewable(conn, body.renewal_of, staff, now)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO submissions (business, dba, state, address, class_of_business, requested_limits, "
                "total_insured_value, brokerage_id, broker_contact, received_on, entered_by, renewal_of) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (body.business, body.dba, body.state, body.address, body.class_of_business, body.requested_limits,
                 body.total_insured_value, body.brokerage_id, body.broker_contact, received_on, staff.id,
                 body.renewal_of),
            )
    except sqlite3.IntegrityError as exc:
        if "submissions.renewal_of" not in str(exc):
            raise
        raise Problem(409, "renewal_open", f"Policy {body.renewal_of} already has a renewal open.") from exc
    return submission_summary(conn, cur.lastrowid)


def _check_renewable(conn: sqlite3.Connection, policy_id: int, staff: Staff, now: datetime) -> None:
    bring_book_to_date(conn, staff, now)
    policy = conn.execute("SELECT id, status FROM policies WHERE id = ?", (policy_id,)).fetchone()
    if policy is None:
        raise Problem(422, "unknown_policy", f"There is no policy {policy_id}.")
    if lapsed(conn, policy):
        raise Problem(409, "policy_lapsed",
                      f"Policy {policy_id} ended with no renewal bound; send the business in as new business.")
    if policy["status"] != "in_force":
        raise Problem(422, "policy_not_in_force", f"Policy {policy_id} is {policy['status']}.")
    if renewal_term(conn, policy_id) is not None:
        raise Problem(409, "renewal_bound", f"Policy {policy_id} already has its renewal term bound.")
    if conn.execute("SELECT 1 FROM submissions WHERE renewal_of = ? AND status IN ('open', 'referred', 'quoted')",
                    (policy_id,)).fetchone():
        raise Problem(409, "renewal_open", f"Policy {policy_id} already has a renewal open.")


@router.get("/{submission_id}")
def show(
    submission_id: RecordId,
    staff: Staff = Depends(signed_in),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    detail = submission_summary(conn, submission_id)
    if staff.role in UNDERWRITING:
        detail["inspections_and_calls"] = list_contacts(conn, submission_id)
        detail["facts"] = list_facts(conn, submission_id)
    return detail


@router.post("/{submission_id}/inspections", status_code=201)
def add_contact(
    submission_id: RecordId,
    body: NewContact,
    request: Request,
    staff: Staff = Depends(underwriting_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    get_submission(conn, submission_id)
    held_on = not_after_today(body.held_on, request.app.state.clock().date(), "held_on")
    with conn:
        cur = conn.execute(
            "INSERT INTO inspections_and_calls (submission_id, kind, with_whom, held_on, recorded_by, findings) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (submission_id, body.kind, body.with_whom, held_on, staff.id, body.findings),
        )
    return {"id": cur.lastrowid, "submission_id": submission_id, "kind": body.kind, "with_whom": body.with_whom,
            "held_on": held_on, "recorded_by": staff.name, "findings": body.findings}


@router.post("/{submission_id}/facts", status_code=201)
def add_fact(
    submission_id: RecordId,
    body: NewFact,
    request: Request,
    staff: Staff = Depends(underwriting_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    get_submission(conn, submission_id)
    checked_on = not_after_today(body.checked_on, request.app.state.clock().date(), "checked_on")
    note = body.note or ""
    with conn:
        cur = conn.execute(
            "INSERT INTO facts (submission_id, field, value, checked_on, checked_by, note) VALUES (?, ?, ?, ?, ?, ?)",
            (submission_id, body.field, body.value, checked_on, staff.id, note),
        )
    return {"id": cur.lastrowid, "submission_id": submission_id, "field": body.field, "value": body.value,
            "checked_on": checked_on, "checked_by": staff.name, "note": note}


@router.post("/{submission_id}/notes", status_code=201)
def add_note(
    submission_id: RecordId,
    body: NewNote,
    request: Request,
    staff: Staff = Depends(underwriting_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    get_submission(conn, submission_id)
    with conn:
        return insert_note(conn, submission_id, staff, body.body, request.app.state.clock())


@router.post("/{submission_id}/decide")
def decide_submission(
    submission_id: RecordId,
    body: Decision,
    request: Request,
    staff: Staff = Depends(underwriting_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    now = request.app.state.clock()
    bring_book_to_date(conn, staff, now)
    submission = get_submission(conn, submission_id)
    decide(conn, submission, staff, body.action, body.model_dump(exclude={"action"}), now)
    return submission_summary(conn, submission_id)
