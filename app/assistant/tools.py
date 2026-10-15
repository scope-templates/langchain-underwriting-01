import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from langchain_core.tools import InjectedToolArg, tool

from app import activity, book
from app import submissions as records
from app.auth import Staff
from app.fields import NoteText


@dataclass(frozen=True)
class Desk:
    conn: sqlite3.Connection
    submission_id: int
    staff: Staff
    clock: Callable[[], datetime]


DeskArg = Annotated[Desk, InjectedToolArg]


def record_activity(desk: Desk, action: str, detail: str, at: datetime) -> None:
    """Appends an activity entry about the question's submission; the caller owns the transaction."""
    activity.log(desk.conn, desk.staff.id, action, detail, at, submission_id=desk.submission_id)


@tool
def submission_summary(submission_id: int, desk: DeskArg) -> dict:
    """The submission: business and DBA, state, address, class of business, requested limits, total insured
    value, brokerage and broker contact, date received, who entered it, the policy it renews if any, status,
    who decided it and when, the annual premium, deductible and terms if quoted, the policy a bind opened, its
    notes, and its decision entries (who quoted, declined, confirmed, bound or marked it not taken, and when)."""
    return records.submission_summary(desk.conn, submission_id)


@tool
def inspections(submission_id: int, desk: DeskArg) -> list[dict]:
    """Inspection reports and broker calls on the submission: kind, with whom, the date, who recorded it, and
    the findings as typed."""
    return records.list_contacts(desk.conn, submission_id)


@tool
def facts(submission_id: int, desk: DeskArg) -> list[dict]:
    """Fact rows the desk holds on the business: field, value, checked_on, checked_by and the checker's note."""
    return records.list_facts(desk.conn, submission_id)


@tool
def loss_history(submission_id: int, desk: DeskArg) -> dict:
    """For a renewal: the expiring policy and each earlier term it renews, with every claim's date of loss,
    date reported, kind, paid, reserve and status, and totals. Returns {"expiring_policy": null} when the
    submission is new business."""
    expiring = records.get_submission(desk.conn, submission_id)["renewal_of"]
    if expiring is None:
        return {"expiring_policy": None}
    return {"expiring_policy": expiring, **book.loss_history(desk.conn, expiring)}


@tool
def save_note(submission_id: int, body: NoteText, desk: DeskArg) -> dict:
    """Save a note of up to 2,000 characters on the submission, written under the name of the person asking
    the question."""
    written_at = desk.clock()
    with desk.conn:
        note = records.insert_note(desk.conn, submission_id, desk.staff, body, written_at)
        record_activity(desk, "save_note", f"note {note['id']}", written_at)
    return note


DESK_TOOLS = (submission_summary, inspections, facts, loss_history, save_note)
SCOPED_TO_SUBMISSION = frozenset(t.name for t in DESK_TOOLS)
TOOLS = list(DESK_TOOLS)
