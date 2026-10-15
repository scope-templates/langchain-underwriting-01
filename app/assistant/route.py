import sqlite3

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.assistant.loop import run
from app.assistant.tools import Desk
from app.auth import Staff, underwriting_staff
from app.book import bring_book_to_date
from app.db import get_db
from app.fields import RecordId, text
from app.problems import Problem
from app.submissions import get_submission

router = APIRouter()


class Question(BaseModel):
    question: text(4000)


@router.post("/assistant/submissions/{submission_id}")
def ask(
    submission_id: RecordId,
    body: Question,
    request: Request,
    staff: Staff = Depends(underwriting_staff),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    get_submission(conn, submission_id)
    model = request.app.state.model_factory()
    if model is None:
        raise Problem(503, "assistant_unconfigured", "OPENAI_API_KEY is unset on this server, or holds a placeholder.")
    clock = request.app.state.clock
    bring_book_to_date(conn, staff, clock())
    return run(model, body.question, Desk(conn, submission_id, staff, clock))
