from datetime import timedelta

from app.auth import Staff
from app.decisions import decide as decide_directly
from app.problems import Problem
from tests.conftest import (CALVIN, JONAH, MARGIT, NOW, PRIYA, TODAY, a_brokerage, a_renewable_policy,
                            new_submission, on, sign_in, staff_id)

EFFECTIVE = (TODAY + timedelta(days=14)).isoformat()


def decide(client, headers, sub_id, **body):
    return client.post(f"/submissions/{sub_id}/decide", headers=headers, json=body)


def entries(db, sub_id):
    return [tuple(r) for r in db.execute(
        "SELECT action, actor, premium, deductible FROM decisions WHERE submission_id = ? ORDER BY id", (sub_id,))]


def quoted(client, db, headers, premium=8400, **extra) -> int:
    sub_id = new_submission(client, headers, db, **extra)
    response = decide(client, headers, sub_id, action="quote", premium=premium, deductible=1000)
    assert response.status_code == 200, response.text
    return sub_id


def renewal(client, db, headers) -> tuple[int, dict]:
    policy_id = a_renewable_policy(db)
    policy = dict(db.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone())
    return quoted(client, db, headers, renewal_of=policy_id), policy


def policy_status(db, policy_id):
    return db.execute("SELECT status FROM policies WHERE id = ?", (policy_id,)).fetchone()[0]


def test_quote_within_authority_is_quoted_and_logs_the_actor(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = new_submission(client, priya, db)
    response = decide(client, priya, sub_id, action="quote", premium=20000, deductible=2500,
                      terms="Hood and duct cleaning every six months")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "quoted" and body["decided_by_name"] == "Priya Ramaswamy"
    assert body["decided_on"] == TODAY.isoformat() and body["annual_premium"] == 20000
    assert body["terms"] == "Hood and duct cleaning every six months"
    assert entries(db, sub_id) == [("quote", staff_id(db, PRIYA), 20000, 2500)]


def test_quote_needs_a_premium_and_a_deductible(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = new_submission(client, priya, db)
    for body in ({"premium": 5000}, {"deductible": 1000}, {}):
        response = decide(client, priya, sub_id, action="quote", **body)
        assert response.status_code == 422 and response.json()["code"] == "quote_incomplete"


def test_premium_above_authority_waits_for_a_senior_who_did_not_quote(client, db):
    margit = sign_in(client, MARGIT)
    sub_id = new_submission(client, margit, db)
    assert decide(client, margit, sub_id, action="quote", premium=20001, deductible=2500).json()["status"] == "referred"

    by_underwriter = decide(client, sign_in(client, PRIYA), sub_id, action="confirm")
    assert by_underwriter.status_code == 403 and by_underwriter.json()["code"] == "role_refused"
    by_quoter = decide(client, margit, sub_id, action="confirm")
    assert by_quoter.status_code == 403 and by_quoter.json()["code"] == "senior_is_quoter"

    confirmed = decide(client, sign_in(client, CALVIN), sub_id, action="confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "quoted"
    assert [e[:2] for e in entries(db, sub_id)] == [("quote", staff_id(db, MARGIT)), ("confirm", staff_id(db, CALVIN))]


def test_insured_value_above_authority_is_referred_at_any_premium(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = new_submission(client, priya, db, total_insured_value=5_000_001)
    assert decide(client, priya, sub_id, action="quote", premium=6000, deductible=5000).json()["status"] == "referred"


def test_confirm_keeps_the_quoted_premium_deductible_and_terms(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = quoted(client, db, priya, premium=31000)
    calvin = sign_in(client, CALVIN)
    for body in ({"premium": 30000}, {"deductible": 5000}, {"terms": "Something else"}):
        response = decide(client, calvin, sub_id, action="confirm", **body)
        assert response.status_code == 422 and response.json()["code"] == "confirm_changes_quote"
    assert decide(client, calvin, sub_id, action="confirm", premium=31000).status_code == 200


def test_decline_closes_an_open_or_referred_submission(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = new_submission(client, priya, db)
    assert decide(client, priya, sub_id, action="decline").json()["status"] == "declined"
    assert entries(db, sub_id) == [("decline", staff_id(db, PRIYA), None, None)]
    again = decide(client, priya, sub_id, action="quote", premium=1000, deductible=500)
    assert again.status_code == 409 and again.json()["code"] == "submission_decided"

    referred = quoted(client, db, priya, premium=25000)
    body = decide(client, sign_in(client, MARGIT), referred, action="decline").json()
    assert body["status"] == "declined" and body["decided_by_name"] == "Margit Olafsen"


def test_quoted_submission_is_bound_or_not_taken_and_nothing_else(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = quoted(client, db, priya)
    late = decide(client, priya, sub_id, action="decline")
    assert late.status_code == 409 and late.json()["code"] == "submission_decided"
    assert decide(client, priya, sub_id, action="not_taken").json()["status"] == "not_taken"
    after = decide(client, priya, sub_id, action="bind", effective=EFFECTIVE, carrier="Callander Indemnity Company")
    assert after.status_code == 409 and after.json()["code"] == "not_quoted"


def test_bind_needs_a_quoted_submission(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = new_submission(client, priya, db)
    response = decide(client, priya, sub_id, action="bind", effective=EFFECTIVE, carrier="Coteau Casualty Company")
    assert response.status_code == 409 and response.json()["code"] == "not_quoted"


def test_binding_new_business_opens_a_policy(client, db):
    jonah = sign_in(client, JONAH)
    sub_id = quoted(client, db, jonah, premium=9100)
    response = decide(client, jonah, sub_id, action="bind", effective=EFFECTIVE, carrier="Coteau Casualty Company")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "bound"
    policy = db.execute("SELECT * FROM policies WHERE id = ?", (body["policy_id"],)).fetchone()
    assert (policy["insured"], policy["status"], policy["annual_premium"], policy["carrier"]) == (
        "Okerlund Hospitality LLC", "pending", 9100, "Coteau Casualty Company")
    assert (policy["effective"], policy["expires"]) == (EFFECTIVE, (TODAY + timedelta(days=14 + 365)).isoformat())
    assert policy["submission_id"] == sub_id and policy["limits"] == "GL $1M/$2M; liquor $1M"
    assert entries(db, sub_id)[-1] == ("bind", staff_id(db, JONAH), 9100, 1000)


def test_binding_new_business_needs_an_effective_date_in_range_and_a_carrier(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = quoted(client, db, priya)
    for body, code in (({"carrier": "Callander Indemnity Company"}, "bind_incomplete"),
                       ({"effective": EFFECTIVE}, "bind_incomplete"),
                       ({"effective": (TODAY - timedelta(days=1)).isoformat(),
                         "carrier": "Callander Indemnity Company"}, "effective_out_of_range"),
                       ({"effective": (TODAY + timedelta(days=91)).isoformat(),
                         "carrier": "Callander Indemnity Company"}, "effective_out_of_range")):
        response = decide(client, priya, sub_id, action="bind", **body)
        assert response.status_code == 422 and response.json()["code"] == code
    unknown = decide(client, priya, sub_id, action="bind", effective=EFFECTIVE, carrier="Some Other Mutual")
    assert unknown.status_code == 422
    assert [e[0] for e in entries(db, sub_id)] == ["quote"]


def test_new_business_bound_to_start_today_is_in_force_at_once(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = quoted(client, db, priya)
    body = decide(client, priya, sub_id, action="bind", effective=TODAY.isoformat(),
                  carrier="Callander Indemnity Company").json()
    assert policy_status(db, body["policy_id"]) == "in_force"


def test_a_bound_renewal_waits_for_the_expiring_term_to_end(make_client, client, db):
    priya = sign_in(client, PRIYA)
    sub_id, expiring = renewal(client, db, priya)
    body = decide(client, priya, sub_id, action="bind").json()
    assert body["status"] == "bound"
    policy = db.execute("SELECT * FROM policies WHERE id = ?", (body["policy_id"],)).fetchone()
    assert policy["prior_policy_id"] == expiring["id"] and policy["effective"] == expiring["expires"]
    assert policy["carrier"] == expiring["carrier"]
    assert (policy["status"], policy_status(db, expiring["id"])) == ("pending", "in_force")

    later = make_client(clock=on(expiring["expires"]))
    later.get("/policies", headers=sign_in(later, PRIYA))
    assert (policy_status(db, policy["id"]), policy_status(db, expiring["id"])) == ("in_force", "expired")


def test_renewal_takes_effect_the_day_the_expiring_policy_ends(client, db):
    priya = sign_in(client, PRIYA)
    sub_id, _ = renewal(client, db, priya)
    response = decide(client, priya, sub_id, action="bind", effective=EFFECTIVE)
    assert response.status_code == 422 and response.json()["code"] == "renewal_effective_fixed"


def test_a_declined_renewal_leaves_the_term_in_force_until_it_ends_non_renewed(make_client, client, db):
    priya = sign_in(client, PRIYA)
    policy = db.execute("SELECT * FROM policies WHERE id = ?", (a_renewable_policy(db),)).fetchone()
    sub_id = new_submission(client, priya, db, renewal_of=policy["id"])
    decide(client, priya, sub_id, action="decline")
    assert policy_status(db, policy["id"]) == "in_force"
    later = make_client(clock=on(policy["expires"]))
    later.get("/policies", headers=sign_in(later, PRIYA))
    assert policy_status(db, policy["id"]) == "non_renewed"


def test_a_renewal_not_taken_leaves_the_term_in_force_until_it_ends_non_renewed(make_client, client, db):
    priya = sign_in(client, PRIYA)
    sub_id, expiring = renewal(client, db, priya)
    decide(client, priya, sub_id, action="not_taken")
    assert policy_status(db, expiring["id"]) == "in_force"
    later = make_client(clock=on(expiring["expires"]))
    later.get("/policies", headers=sign_in(later, PRIYA))
    assert policy_status(db, expiring["id"]) == "non_renewed"


def test_a_policy_has_one_open_renewal_at_a_time(client, db):
    priya = sign_in(client, PRIYA)
    first, expiring = renewal(client, db, priya)
    response = client.post("/submissions", headers=priya, json={
        "business": "Okerlund Hospitality LLC", "state": "IA", "address": "410 Commerce St, Hesper Mills, IA",
        "class_of_business": "tavern", "requested_limits": "GL $1M/$2M", "total_insured_value": 250000,
        "brokerage_id": a_brokerage(db), "broker_contact": "Dana Whitcomb", "renewal_of": expiring["id"]})
    assert response.status_code == 409 and response.json()["code"] == "renewal_open"
    assert decide(client, priya, first, action="bind").status_code == 200
    assert db.execute("SELECT count(*) FROM policies WHERE prior_policy_id = ?", (expiring["id"],)).fetchone()[0] == 1


def test_two_decisions_from_one_status_cannot_both_land(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = new_submission(client, priya, db)
    first_read = db.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    assert decide(client, priya, sub_id, action="decline").status_code == 200

    actor = Staff(staff_id(db, PRIYA), "Priya Ramaswamy", PRIYA, "underwriter")
    try:
        decide_directly(db, first_read, actor, "quote", {"premium": 5000, "deductible": 1000}, NOW)
    except Problem as problem:
        assert (problem.status, problem.code) == (409, "status_changed")
    else:
        raise AssertionError("the second decision landed")
    assert [e[0] for e in entries(db, sub_id)] == ["decline"]
