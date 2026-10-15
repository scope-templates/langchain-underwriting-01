import shutil
from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient

from app.db import connect, init_db
from app.main import create_app
from app.seed import ensure_seeded

NOW = datetime(2026, 10, 1, 10, 0, 0)
TODAY = NOW.date()

MARGIT = "margit.olafsen@ketterlyuw.com"
CALVIN = "calvin.ruehl@ketterlyuw.com"
PRIYA = "priya.ramaswamy@ketterlyuw.com"
JONAH = "jonah.feldkamp@ketterlyuw.com"
GRETCHEN = "gretchen.hasselbring@ketterlyuw.com"


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("seed") / "desk.db"
    init_db(path)
    ensure_seeded(path)
    return path


@pytest.fixture
def db_path(seeded_db, tmp_path):
    path = tmp_path / "desk.db"
    shutil.copy(seeded_db, path)
    return path


@pytest.fixture
def db(db_path):
    conn = connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def make_client(db_path):
    def build(model=None, model_factory=None, clock=lambda: NOW, **client_args) -> TestClient:
        app = create_app(db_path, model_factory=model_factory or (lambda: model), clock=clock)
        return TestClient(app, **client_args)

    return build


@pytest.fixture
def client(make_client):
    return make_client()


def on(day: str):
    """A clock that reads 9 a.m. on `day`."""
    return lambda: datetime.combine(date.fromisoformat(day), time(9, 0))


def sign_in(client: TestClient, email: str) -> dict:
    response = client.post("/session", json={"email": email})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def staff_id(conn, email: str) -> int:
    return conn.execute("SELECT id FROM staff WHERE email = ?", (email,)).fetchone()["id"]


def a_submission(conn, status: str = "open", renewal: bool | None = None) -> int:
    sql = "SELECT id FROM submissions WHERE status = ?"
    if renewal is not None:
        sql += " AND renewal_of IS NOT NULL" if renewal else " AND renewal_of IS NULL"
    return conn.execute(sql + " ORDER BY id LIMIT 1", (status,)).fetchone()["id"]


def other_submission(conn, submission_id: int) -> int:
    return conn.execute("SELECT id FROM submissions WHERE id <> ? ORDER BY id LIMIT 1",
                        (submission_id,)).fetchone()["id"]


def a_brokerage(conn, status: str = "active") -> int:
    return conn.execute("SELECT id FROM brokerages WHERE status = ? ORDER BY id LIMIT 1", (status,)).fetchone()["id"]


def a_renewable_policy(conn) -> int:
    """An in-force policy that no submission renews yet."""
    return conn.execute(
        "SELECT id FROM policies p WHERE status = 'in_force' AND expires > '2026-10-01' "
        "AND NOT EXISTS (SELECT 1 FROM submissions s WHERE s.renewal_of = p.id) ORDER BY id LIMIT 1"
    ).fetchone()["id"]


def new_submission(client: TestClient, headers: dict, conn, total_insured_value: int = 400_000, **extra) -> int:
    response = client.post("/submissions", headers=headers, json={
        "business": "Okerlund Hospitality LLC",
        "dba": "The Wren Table",
        "state": "IA",
        "address": "410 Commerce St, Hesper Mills, IA 50628",
        "class_of_business": "full-service restaurant",
        "requested_limits": "GL $1M/$2M; liquor $1M",
        "total_insured_value": total_insured_value,
        "brokerage_id": a_brokerage(conn),
        "broker_contact": "Dana Whitcomb",
        **extra,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]
