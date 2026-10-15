from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI

from app import auth, book, problems, submissions
from app.assistant import route as assistant
from app.assistant.model import build_model
from app.db import init_db
from app.seed import ensure_seeded

DEFAULT_DB = Path(__file__).resolve().parent.parent / "desk.db"


def local_now() -> datetime:
    return datetime.now().replace(microsecond=0)


def create_app(
    db_path: str | Path = DEFAULT_DB,
    model_factory: Callable = build_model,
    clock: Callable[[], datetime] = local_now,
) -> FastAPI:
    init_db(db_path)
    ensure_seeded(db_path)
    app = FastAPI(title="Ketterly underwriting desk")
    app.state.db_path = str(db_path)
    app.state.model_factory = model_factory
    app.state.clock = clock
    problems.install(app)
    for module in (auth, submissions, book, assistant):
        app.include_router(module.router)
    return app
