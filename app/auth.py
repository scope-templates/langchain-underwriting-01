import hashlib
import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.db import get_db
from app.fields import text
from app.problems import Problem

UNDERWRITING = ("underwriter", "senior")
SESSION_MAX_AGE = timedelta(days=30)

router = APIRouter()


@dataclass(frozen=True)
class Staff:
    id: int
    name: str
    email: str
    role: str


class SessionRequest(BaseModel):
    email: text(200)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _bearer(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Problem(401, "unauthenticated", "Send a bearer token from POST /session.")
    return token


@router.post("/session")
def open_session(body: SessionRequest, request: Request, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    row = conn.execute(
        "SELECT id, name, email, role FROM staff WHERE lower(email) = lower(?)", (body.email,)
    ).fetchone()
    if row is None:
        raise Problem(401, "unknown_staff", "No staff member has that email.")
    token = secrets.token_urlsafe(32)
    now = request.app.state.clock()
    with conn:
        conn.execute("DELETE FROM sessions WHERE created_at < ?", ((now - SESSION_MAX_AGE).isoformat(),))
        conn.execute(
            "INSERT INTO sessions (token_hash, staff_id, created_at) VALUES (?, ?, ?)",
            (_hash(token), row["id"], now.isoformat()),
        )
    return {"token": token, "staff": dict(row)}


@router.delete("/session", status_code=204)
def close_session(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> Response:
    with conn:
        cur = conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(_bearer(request)),))
    if cur.rowcount == 0:
        raise Problem(401, "unauthenticated", "That token does not match a session.")
    return Response(status_code=204)


def signed_in(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> Staff:
    row = conn.execute(
        "SELECT s.id, s.name, s.email, s.role FROM sessions x JOIN staff s ON s.id = x.staff_id "
        "WHERE x.token_hash = ? AND x.created_at >= ?",
        (_hash(_bearer(request)), (request.app.state.clock() - SESSION_MAX_AGE).isoformat()),
    ).fetchone()
    if row is None:
        raise Problem(401, "unauthenticated", "That token does not match a session from the last 30 days.")
    return Staff(**dict(row))


def staff_in(*roles: str) -> Callable[..., Staff]:
    """A dependency for the signed-in person, refused with 403 unless their role is one of `roles`. Dependencies
    run before the request body is validated, so a refused role gets its 403 whatever the body holds."""

    def check(staff: Staff = Depends(signed_in)) -> Staff:
        if staff.role not in roles:
            raise Problem(403, "role_refused", f"The {staff.role} role cannot do this.")
        return staff

    return check


underwriting_staff = staff_in(*UNDERWRITING)
senior_staff = staff_in("senior")
