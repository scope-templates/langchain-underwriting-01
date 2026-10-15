import sqlite3
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app import activity
from app.auth import Staff, senior_staff, signed_in
from app.db import BROKERAGE_STATUSES, POLICY_STATUSES, ends_non_renewed, get_db
from app.fields import Day, Paid, RecordId, not_after_today, text
from app.problems import Problem

router = APIRouter()

POLICY_COLUMNS = ("p.id, p.insured, p.state, p.carrier, b.name AS brokerage, p.effective, p.expires, "
                  "p.annual_premium, p.limits, p.status, p.cancelled_on, p.prior_policy_id, p.submission_id")


class Cancellation(BaseModel):
    cancelled_on: Day
    reason: text(500)


class ClaimClosing(BaseModel):
    paid: Paid


class BrokerageStatus(BaseModel):
    status: Literal[BROKERAGE_STATUSES]


def _filtered(sql: str, column: str, status: str | None, order: str) -> tuple[str, tuple]:
    if status is None:
        return f"{sql} ORDER BY {order}", ()
    return f"{sql} WHERE {column} = ? ORDER BY {order}", (status,)


def bring_book_to_date(conn: sqlite3.Connection, actor: Staff, now: datetime) -> None:
    """Moves each policy whose effective date has come from `pending` to `in_force`, and each whose term has ended
    from `in_force` to `non_renewed` (its renewal declined or not taken, and no renewal term) or `expired`, with a
    `policy_started` or `policy_ended` activity entry for each. Runs before the desk reads or decides on policies."""
    today, at = now.date().isoformat(), now.isoformat()
    with conn:
        conn.execute(
            "INSERT INTO activity (actor, action, policy_id, detail, at) SELECT ?, 'policy_started', id, "
            "'term began ' || effective, ? FROM policies WHERE status = 'pending' AND effective <= ? ORDER BY id",
            (actor.id, at, today),
        )
        conn.execute("UPDATE policies SET status = 'in_force' WHERE status = 'pending' AND effective <= ?", (today,))
        conn.execute(
            "INSERT INTO activity (actor, action, policy_id, detail, at) SELECT ?, 'policy_ended', id, "
            "'term ended ' || expires, ? FROM policies WHERE status = 'in_force' AND expires <= ? ORDER BY id",
            (actor.id, at, today),
        )
        conn.execute(
            f"UPDATE policies SET status = CASE WHEN {ends_non_renewed('policies.id')} THEN 'non_renewed' "
            "ELSE 'expired' END WHERE status = 'in_force' AND expires <= ?",
            (today,),
        )


def get_policy(conn: sqlite3.Connection, policy_id: int) -> sqlite3.Row:
    row = conn.execute(
        f"SELECT {POLICY_COLUMNS} FROM policies p JOIN brokerages b ON b.id = p.brokerage_id WHERE p.id = ?",
        (policy_id,),
    ).fetchone()
    if row is None:
        raise Problem(404, "not_found", f"There is no policy {policy_id}.")
    return row


def renewal_term(conn: sqlite3.Connection, policy_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT id, status FROM policies WHERE prior_policy_id = ?", (policy_id,)).fetchone()


def lapsed(conn: sqlite3.Connection, policy: sqlite3.Row) -> bool:
    """A policy whose term ended with no renewal term after it: its insured comes back as new business."""
    return policy["status"] in ("expired", "non_renewed") and renewal_term(conn, policy["id"]) is None


def loss_history(conn: sqlite3.Connection, policy_id: int) -> dict:
    """The policy and each earlier term it renews, newest first, each with its claims, and totals across them."""
    terms = []
    next_id: int | None = policy_id
    while next_id is not None:
        term = dict(get_policy(conn, next_id))
        term["claims"] = [
            dict(c)
            for c in conn.execute(
                "SELECT id, date_of_loss, reported_on, kind, paid, reserve, status FROM claims "
                "WHERE policy_id = ? ORDER BY date_of_loss, id",
                (next_id,),
            )
        ]
        term["paid"] = sum(c["paid"] for c in term["claims"])
        term["reserve"] = sum(c["reserve"] for c in term["claims"])
        terms.append(term)
        next_id = term["prior_policy_id"]
    return {"policy_id": policy_id, "terms": terms, "claims": sum(len(t["claims"]) for t in terms),
            "paid": sum(t["paid"] for t in terms), "reserve": sum(t["reserve"] for t in terms)}


@router.get("/brokerages")
def brokerages(
    status: Literal[BROKERAGE_STATUSES] | None = None,
    staff: Staff = Depends(signed_in),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    sql, args = _filtered("SELECT * FROM brokerages", "status", status, "name, id")
    return [dict(r) for r in conn.execute(sql, args)]


@router.post("/brokerages/{brokerage_id}/status")
def set_brokerage_status(
    brokerage_id: RecordId,
    body: BrokerageStatus,
    request: Request,
    staff: Staff = Depends(senior_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute("SELECT * FROM brokerages WHERE id = ?", (brokerage_id,)).fetchone()
    if row is None:
        raise Problem(404, "not_found", f"There is no brokerage {brokerage_id}.")
    if row["status"] == body.status:
        raise Problem(409, "status_unchanged", f"Brokerage {brokerage_id} is already {body.status}.")
    with conn:
        activity.log(conn, staff.id, "brokerage_status", body.status, request.app.state.clock(),
                     brokerage_id=brokerage_id)
        cur = conn.execute("UPDATE brokerages SET status = ? WHERE id = ? AND status = ?",
                           (body.status, brokerage_id, row["status"]))
        if cur.rowcount == 0:
            raise Problem(409, "status_changed", f"Brokerage {brokerage_id} is no longer {row['status']}.")
    return dict(conn.execute("SELECT * FROM brokerages WHERE id = ?", (brokerage_id,)).fetchone())


@router.get("/policies")
def policies(
    request: Request,
    status: Literal[POLICY_STATUSES] | None = None,
    staff: Staff = Depends(signed_in),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    bring_book_to_date(conn, staff, request.app.state.clock())
    sql, args = _filtered(f"SELECT {POLICY_COLUMNS} FROM policies p JOIN brokerages b ON b.id = p.brokerage_id",
                          "p.status", status, "p.effective DESC, p.id DESC")
    return [dict(r) for r in conn.execute(sql, args)]


@router.get("/policies/{policy_id}/losses")
def losses(
    policy_id: RecordId,
    request: Request,
    staff: Staff = Depends(signed_in),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    bring_book_to_date(conn, staff, request.app.state.clock())
    return loss_history(conn, policy_id)


@router.post("/policies/{policy_id}/cancel")
def cancel_policy(
    policy_id: RecordId,
    body: Cancellation,
    request: Request,
    staff: Staff = Depends(senior_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    now = request.app.state.clock()
    bring_book_to_date(conn, staff, now)
    policy = get_policy(conn, policy_id)
    if policy["status"] not in ("pending", "in_force"):
        raise Problem(409, "policy_not_in_force", f"Policy {policy_id} is {policy['status']}.")
    if policy["status"] == "pending":
        day = body.cancelled_on.isoformat()
        if day != policy["effective"]:
            raise Problem(422, "flat_cancellation_only",
                          f"Policy {policy_id} has not started; it is cancelled as of its effective date, "
                          f"{policy['effective']}.")
    else:
        day = not_after_today(body.cancelled_on, now.date(), "cancelled_on")
    if not policy["effective"] <= day < policy["expires"]:
        raise Problem(422, "outside_term", f"Policy {policy_id} runs {policy['effective']} to {policy['expires']}.")
    last_loss = conn.execute("SELECT max(date_of_loss) FROM claims WHERE policy_id = ?", (policy_id,)).fetchone()[0]
    if last_loss is not None and day <= last_loss:
        raise Problem(422, "loss_on_or_after_cancellation",
                      f"Policy {policy_id} has a loss on {last_loss}; it can be cancelled only after that day.")
    with conn:
        activity.log(conn, staff.id, "policy_cancelled", f"cancelled as of {day}: {body.reason}", now,
                     policy_id=policy_id)
        cur = conn.execute("UPDATE policies SET status = 'cancelled', cancelled_on = ? WHERE id = ? AND status = ?",
                           (day, policy_id, policy["status"]))
        if cur.rowcount == 0:
            raise Problem(409, "status_changed", f"Policy {policy_id} is no longer {policy['status']}.")
    return dict(get_policy(conn, policy_id))


@router.post("/claims/{claim_id}/close")
def close_claim(
    claim_id: RecordId,
    body: ClaimClosing,
    request: Request,
    staff: Staff = Depends(senior_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if claim is None:
        raise Problem(404, "not_found", f"There is no claim {claim_id}.")
    if claim["status"] != "open":
        raise Problem(409, "claim_closed", f"Claim {claim_id} is already closed.")
    if body.paid < claim["paid"]:
        raise Problem(422, "paid_lowered", f"Claim {claim_id} has ${claim['paid']:,} paid already.")
    with conn:
        activity.log(conn, staff.id, "claim_closed", f"closed with ${body.paid:,} paid", request.app.state.clock(),
                     claim_id=claim_id)
        cur = conn.execute(
            "UPDATE claims SET status = 'closed', paid = ?, reserve = 0 WHERE id = ? AND status = 'open'",
            (body.paid, claim_id))
        if cur.rowcount == 0:
            raise Problem(409, "status_changed", f"Claim {claim_id} is no longer open.")
    return dict(conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone())
