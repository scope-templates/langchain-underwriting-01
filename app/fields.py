from datetime import date
from typing import Annotated

from fastapi import Path
from pydantic import Field, StringConstraints

from app.problems import Problem

MAX_ID = 2**31 - 1
MAX_PREMIUM = 1_000_000
MAX_DEDUCTIBLE = 250_000
MAX_INSURED_VALUE = 100_000_000
MAX_PAID = 10_000_000

RecordId = Annotated[int, Path(ge=1, le=MAX_ID)]
Premium = Annotated[int, Field(gt=0, le=MAX_PREMIUM, strict=True)]
Deductible = Annotated[int, Field(gt=0, le=MAX_DEDUCTIBLE, strict=True)]
InsuredValue = Annotated[int, Field(gt=0, le=MAX_INSURED_VALUE, strict=True)]
Paid = Annotated[int, Field(ge=0, le=MAX_PAID, strict=True)]
Day = Annotated[date, Field(ge=date(1990, 1, 1), le=date(2040, 12, 31))]


def text(max_length: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)]


NoteText = text(2000)


def not_after_today(day: date, today: date, what: str) -> str:
    if day > today:
        raise Problem(422, "future_date", f"{what} {day.isoformat()} is after today ({today.isoformat()}).")
    return day.isoformat()
