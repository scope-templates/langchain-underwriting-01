from datetime import timedelta

from langchain_core.messages import AIMessage

from tests.conftest import GRETCHEN, NOW, PRIYA, a_submission, sign_in
from tests.fake_model import FakeChatModel


def test_session_refuses_an_unknown_email(client):
    response = client.post("/session", json={"email": "someone@elsewhere.test"})
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "unknown_staff"


def test_routes_need_a_bearer_token(client):
    for response in (client.get("/submissions"), client.get("/policies", headers={"Authorization": "Bearer nope"})):
        assert response.status_code == 401
        assert response.json()["code"] == "unauthenticated"


def test_session_older_than_thirty_days_is_refused(make_client):
    headers = sign_in(make_client(), PRIYA)
    assert make_client(clock=lambda: NOW + timedelta(days=29)).get("/submissions", headers=headers).status_code == 200
    later = make_client(clock=lambda: NOW + timedelta(days=31)).get("/submissions", headers=headers)
    assert later.status_code == 401 and later.json()["code"] == "unauthenticated"


def test_signing_in_clears_sessions_past_their_age(make_client, db):
    sign_in(make_client(), PRIYA)
    sign_in(make_client(), GRETCHEN)
    assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 2
    sign_in(make_client(clock=lambda: NOW + timedelta(days=31)), PRIYA)
    assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1


def test_viewer_reads_a_submission_without_inspections_or_facts(client, db):
    sub_id = a_submission(db, "bound")
    viewer = client.get(f"/submissions/{sub_id}", headers=sign_in(client, GRETCHEN)).json()
    underwriter = client.get(f"/submissions/{sub_id}", headers=sign_in(client, PRIYA)).json()
    assert "inspections_and_calls" not in viewer and "facts" not in viewer
    assert viewer["id"] == sub_id and viewer["notes"] and viewer["decisions"]
    assert underwriter["inspections_and_calls"] and underwriter["facts"]


def test_viewer_reads_the_book(client):
    headers = sign_in(client, GRETCHEN)
    for path in ("/submissions", "/policies", "/policies/1/losses", "/brokerages"):
        assert client.get(path, headers=headers).status_code == 200, path


def test_viewer_cannot_write_or_decide(client, db):
    headers = sign_in(client, GRETCHEN)
    sub_id = a_submission(db)
    attempts = [
        client.post("/submissions", headers=headers, json={
            "business": "X LLC", "state": "IA", "address": "1 Elm St", "class_of_business": "tavern",
            "requested_limits": "GL $1M/$2M", "total_insured_value": 100000, "brokerage_id": 1,
            "broker_contact": "Dana"}),
        client.post(f"/submissions/{sub_id}/facts", headers=headers, json={
            "field": "owner", "value": "X", "checked_on": "2026-09-01"}),
        client.post(f"/submissions/{sub_id}/inspections", headers=headers, json={
            "kind": "broker_call", "with_whom": "X", "held_on": "2026-09-01", "findings": "X"}),
        client.post(f"/submissions/{sub_id}/notes", headers=headers, json={"body": "X"}),
        client.post(f"/submissions/{sub_id}/decide", headers=headers, json={"action": "decline"}),
    ]
    for response in attempts:
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "role_refused"


def test_assistant_route_refuses_viewers(make_client, db):
    model = FakeChatModel(replies=[AIMessage(content="hello")])
    client = make_client(model)
    response = client.post(f"/assistant/submissions/{a_submission(db)}", headers=sign_in(client, GRETCHEN),
                           json={"question": "What did the inspection find?"})
    assert response.status_code == 403
    assert response.json()["code"] == "role_refused"
    assert model.calls == []
