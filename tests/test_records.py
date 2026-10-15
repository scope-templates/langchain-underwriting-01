import json
from datetime import timedelta

import app.book
from app.seed import SEED_FILE, rows_of
from tests.conftest import (GRETCHEN, PRIYA, TODAY, a_brokerage, a_renewable_policy, a_submission, new_submission,
                            sign_in, staff_id)


def post_fact(client, headers, sub_id, **body):
    return client.post(f"/submissions/{sub_id}/facts", headers=headers, json=body)


def submission_body(db, **extra) -> dict:
    return {"business": "Okerlund Hospitality LLC", "state": "IA", "address": "410 Commerce St, Hesper Mills, IA",
            "class_of_business": "tavern", "requested_limits": "GL $1M/$2M", "total_insured_value": 250000,
            "brokerage_id": a_brokerage(db), "broker_contact": "Dana Whitcomb", **extra}


def test_new_submission_is_open_and_names_who_entered_it(client, db):
    priya = sign_in(client, PRIYA)
    body = client.get(f"/submissions/{new_submission(client, priya, db)}", headers=priya).json()
    assert body["status"] == "open" and body["entered_by_name"] == "Priya Ramaswamy"
    assert body["received_on"] == TODAY.isoformat() and body["brokerage"]
    assert body["inspections_and_calls"] == [] and body["facts"] == [] and body["policy_id"] is None


def test_new_submission_refusals(client, db):
    priya = sign_in(client, PRIYA)
    in_force = a_renewable_policy(db)
    non_renewed = db.execute("SELECT id FROM policies WHERE status = 'non_renewed' ORDER BY id LIMIT 1").fetchone()[0]
    pending = db.execute("SELECT id FROM policies WHERE status = 'pending' ORDER BY id LIMIT 1").fetchone()[0]
    cases = [
        ({"brokerage_id": a_brokerage(db, "inactive")}, 422, "brokerage_inactive"),
        ({"brokerage_id": 99999}, 422, "unknown_brokerage"),
        ({"renewal_of": 99999}, 422, "unknown_policy"),
        ({"renewal_of": non_renewed}, 409, "policy_lapsed"),
        ({"renewal_of": pending}, 422, "policy_not_in_force"),
        ({"received_on": "1989-12-29"}, 422, "invalid_request"),
        ({"state": "TX"}, 422, "invalid_request"),
        ({"received_on": (TODAY + timedelta(days=1)).isoformat()}, 422, "future_date"),
    ]
    for extra, status, code in cases:
        response = client.post("/submissions", headers=priya, json=submission_body(db, **extra))
        assert response.status_code == status and response.json()["code"] == code, (extra, response.text)
    renewal = client.post("/submissions", headers=priya, json=submission_body(db, renewal_of=in_force))
    assert renewal.status_code == 201 and renewal.json()["renewal_of"] == in_force


def test_fact_is_checked_by_the_signed_in_person(client, db):
    priya = sign_in(client, PRIYA)
    response = post_fact(client, priya, a_submission(db), field="headcount", value="about 22",
                         checked_on="2026-09-29", note="owner told me on the phone", checked_by=1)
    assert response.status_code == 201, response.text
    row = db.execute("SELECT checked_on, checked_by FROM facts WHERE id = ?", (response.json()["id"],)).fetchone()
    assert tuple(row) == ("2026-09-29", staff_id(db, PRIYA))


def test_fact_needs_a_checked_on_date_not_after_today(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = a_submission(db)
    missing = post_fact(client, priya, sub_id, field="owner", value="X")
    assert missing.status_code == 422 and missing.json()["code"] == "invalid_request"
    tomorrow = post_fact(client, priya, sub_id, field="owner", value="X",
                         checked_on=(TODAY + timedelta(days=1)).isoformat())
    assert tomorrow.status_code == 422 and tomorrow.json()["code"] == "future_date"
    assert post_fact(client, priya, sub_id, field="owner", value="X", checked_on=TODAY.isoformat()).status_code == 201


def test_fact_field_must_be_one_the_desk_uses(client, db):
    response = post_fact(client, sign_in(client, PRIYA), a_submission(db), field="shoe_size", value="x",
                         checked_on="2026-09-01")
    assert response.status_code == 422


def test_blank_text_is_refused(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = a_submission(db)
    attempts = [
        client.post(f"/submissions/{sub_id}/notes", headers=priya, json={"body": "   "}),
        post_fact(client, priya, sub_id, field="owner", value="  ", checked_on="2026-09-01"),
        post_fact(client, priya, sub_id, field="owner", value="X", checked_on="2026-09-01", note=" \n "),
        client.post(f"/submissions/{sub_id}/inspections", headers=priya, json={
            "kind": "broker_call", "with_whom": "Dana", "held_on": "2026-09-01", "findings": "\t"}),
        client.post("/submissions", headers=priya, json=submission_body(db, business="  ")),
        client.post(f"/submissions/{sub_id}/decide", headers=priya, json={"action": "quote", "premium": 5000,
                                                                           "deductible": 500, "terms": " "}),
        client.post("/session", json={"email": "   "}),
    ]
    assert [r.status_code for r in attempts] == [422] * len(attempts)


def test_numbers_have_bounds(client, db):
    priya = sign_in(client, PRIYA)
    huge = 10**20
    assert client.get(f"/submissions/{huge}", headers=priya).status_code == 422
    assert client.get(f"/policies/{huge}/losses", headers=priya).status_code == 422
    for extra in ({"total_insured_value": huge}, {"total_insured_value": 0}, {"brokerage_id": huge}):
        response = client.post("/submissions", headers=priya, json=submission_body(db, **extra))
        assert response.status_code == 422 and response.json()["code"] == "invalid_request"
    for premium in (0, 1_000_001):
        response = client.post(f"/submissions/{a_submission(db)}/decide", headers=priya,
                               json={"action": "quote", "premium": premium, "deductible": 500})
        assert response.status_code == 422


def test_status_filters_are_validated(client):
    priya = sign_in(client, PRIYA)
    for path, good, bad in (("/submissions", "referred", "pending"), ("/policies", "non_renewed", "lapsed"),
                            ("/brokerages", "inactive", "closed")):
        listed = client.get(f"{path}?status={good}", headers=priya)
        assert listed.status_code == 200 and all(r["status"] == good for r in listed.json())
        assert client.get(f"{path}?status={bad}", headers=priya).status_code == 422


def test_inspection_and_note_carry_the_signed_in_person(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = a_submission(db)
    contact = client.post(f"/submissions/{sub_id}/inspections", headers=priya, json={
        "kind": "inspection", "with_whom": "Len Ostby, Kestner Risk Surveys", "held_on": "2026-09-30",
        "findings": "Brick, built 1962, no sprinklers. Hood tagged in August."})
    note = client.post(f"/submissions/{sub_id}/notes", headers=priya, json={"body": "Menu came in."})
    assert contact.status_code == 201 and contact.json()["recorded_by"] == "Priya Ramaswamy"
    assert note.status_code == 201 and note.json()["author"] == "Priya Ramaswamy"
    assert note.json()["written_at"] == "2026-10-01T10:00:00"
    for body in ({"kind": "site_visit"}, {"held_on": "2026-12-01"}):
        response = client.post(f"/submissions/{sub_id}/inspections", headers=priya, json={
            "kind": "broker_call", "with_whom": "Dana", "held_on": "2026-09-30", "findings": "x", **body})
        assert response.status_code == 422


def test_unknown_records_are_problem_404s(client):
    priya = sign_in(client, PRIYA)
    for path in ("/submissions/9999", "/policies/99999/losses"):
        response = client.get(path, headers=priya)
        assert response.status_code == 404 and response.json()["code"] == "not_found"


def test_unexpected_failure_is_a_problem_500(make_client, monkeypatch):
    def broken(*args):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(app.book, "loss_history", broken)
    client = make_client(raise_server_exceptions=False)
    response = client.get("/policies/1/losses", headers=sign_in(client, PRIYA))
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "internal_error"


def test_loss_history_walks_back_through_prior_terms(client, db):
    priya = sign_in(client, PRIYA)
    newest = db.execute(
        "SELECT p.id FROM policies p JOIN policies q ON q.id = p.prior_policy_id "
        "WHERE q.prior_policy_id IS NOT NULL ORDER BY p.id LIMIT 1").fetchone()[0]
    report = client.get(f"/policies/{newest}/losses", headers=priya).json()
    terms = report["terms"]
    assert terms[0]["id"] == newest and len(terms) >= 3
    for later, earlier in zip(terms, terms[1:]):
        assert later["prior_policy_id"] == earlier["id"] and later["effective"] == earlier["expires"]
    assert report["claims"] == sum(len(t["claims"]) for t in terms)
    assert report["paid"] == sum(c["paid"] for t in terms for c in t["claims"])


def test_policies_and_brokerages_list_the_book(client):
    priya = sign_in(client, PRIYA)
    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    assert len(client.get("/policies", headers=priya).json()) == len(rows_of(seed, "policies"))
    assert len(client.get("/brokerages", headers=priya).json()) == len(rows_of(seed, "brokerages"))


def test_money_fields_take_whole_numbers_only(client, db):
    priya = sign_in(client, PRIYA)
    for value in (True, "250000", 250000.0):
        response = client.post("/submissions", headers=priya, json=submission_body(db, total_insured_value=value))
        assert response.status_code == 422, value
    sub_id = a_submission(db)
    response = client.post(f"/submissions/{sub_id}/decide", headers=priya,
                           json={"action": "quote", "premium": True, "deductible": 500})
    assert response.status_code == 422


def test_dates_before_1990_are_refused(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = a_submission(db)
    fact = post_fact(client, priya, sub_id, field="owner", value="X", checked_on="1989-06-01")
    call = client.post(f"/submissions/{sub_id}/inspections", headers=priya, json={
        "kind": "broker_call", "with_whom": "Dana", "held_on": "1970-01-01", "findings": "x"})
    assert [fact.status_code, call.status_code] == [422, 422]


def test_a_viewer_is_refused_before_the_body_is_read(client, db):
    viewer = sign_in(client, GRETCHEN)
    sub_id = a_submission(db)
    for path, body in ((f"/submissions/{sub_id}/facts", {"field": "shoe_size"}),
                       (f"/submissions/{sub_id}/decide", {"action": "dance"}),
                       ("/submissions", {})):
        response = client.post(path, headers=viewer, json=body)
        assert response.status_code == 403 and response.json()["code"] == "role_refused"


def test_a_decision_refuses_fields_its_action_does_not_use(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = a_submission(db)
    for body in ({"action": "decline", "premium": 5000}, {"action": "quote", "premium": 5000, "deductible": 500,
                                                          "carrier": "Coteau Casualty Company"},
                 {"action": "not_taken", "effective": TODAY.isoformat()}):
        response = client.post(f"/submissions/{sub_id}/decide", headers=priya, json=body)
        assert response.status_code == 422 and response.json()["code"] == "field_not_used", body
    assert db.execute("SELECT status FROM submissions WHERE id = ?", (sub_id,)).fetchone()[0] == "open"


def test_signing_out_revokes_the_token(client):
    headers = sign_in(client, PRIYA)
    assert client.delete("/session", headers=headers).status_code == 204
    after = client.get("/submissions", headers=headers)
    assert after.status_code == 401 and after.json()["code"] == "unauthenticated"
    assert client.delete("/session", headers=headers).status_code == 401
