from datetime import datetime, timedelta

from tests.conftest import CALVIN, MARGIT, PRIYA, TODAY, a_brokerage, new_submission, on, sign_in, staff_id


def next_to_lapse(db):
    """The in-force policy that ends soonest after today, with no renewal open."""
    return db.execute(
        "SELECT * FROM policies p WHERE status = 'in_force' AND expires > ? AND NOT EXISTS "
        "(SELECT 1 FROM submissions s WHERE s.renewal_of = p.id) ORDER BY expires, id LIMIT 1",
        (TODAY.isoformat(),)).fetchone()


def a_cancellable_policy(db):
    return db.execute(
        "SELECT * FROM policies p WHERE status = 'in_force' AND effective < ? AND expires > ? AND NOT EXISTS "
        "(SELECT 1 FROM claims c WHERE c.policy_id = p.id) ORDER BY id LIMIT 1",
        (TODAY.isoformat(), TODAY.isoformat())).fetchone()


def status_of(db, table, row_id):
    return db.execute(f"SELECT status FROM {table} WHERE id = ?", (row_id,)).fetchone()[0]


def entries(db, action, since=TODAY.isoformat()):
    return [dict(r) for r in db.execute("SELECT * FROM activity WHERE action = ? AND at >= ? ORDER BY id",
                                        (action, since))]


def test_a_term_ends_on_its_expiry_date(make_client, db):
    policy = next_to_lapse(db)
    client = make_client(clock=on(policy["expires"]))
    priya = sign_in(client, PRIYA)
    assert client.get("/policies", headers=priya).status_code == 200
    assert status_of(db, "policies", policy["id"]) == "expired"
    ended = entries(db, "policy_ended", policy["expires"])
    assert policy["id"] in {e["policy_id"] for e in ended}
    assert all(e["actor"] == staff_id(db, PRIYA) and e["at"][:10] == policy["expires"] for e in ended)
    assert db.execute("SELECT count(*) FROM policies WHERE status = 'in_force' AND expires <= ?",
                      (policy["expires"],)).fetchone()[0] == 0
    client.get("/policies", headers=priya)
    assert len(entries(db, "policy_ended", policy["expires"])) == len(ended)


def test_a_pending_policy_comes_into_force_on_its_effective_date(make_client, db):
    policy = db.execute("SELECT * FROM policies WHERE status = 'pending' ORDER BY effective LIMIT 1").fetchone()
    day_before = (datetime.fromisoformat(policy["effective"]) - timedelta(days=1)).date().isoformat()
    early = make_client(clock=on(day_before))
    early.get("/policies", headers=sign_in(early, PRIYA))
    assert status_of(db, "policies", policy["id"]) == "pending"
    client = make_client(clock=on(policy["effective"]))
    client.get(f"/policies/{policy['id']}/losses", headers=sign_in(client, PRIYA))
    assert status_of(db, "policies", policy["id"]) == "in_force"
    assert policy["id"] in {e["policy_id"] for e in entries(db, "policy_started", policy["effective"])}


def test_a_lapsed_policy_comes_back_as_new_business(make_client, db):
    policy = next_to_lapse(db)
    client = make_client(clock=on(policy["expires"]))
    priya = sign_in(client, PRIYA)
    response = client.post("/submissions", headers=priya, json={
        "business": policy["insured"], "state": policy["state"], "address": "12 Pearl St, Varnell, NE 68852",
        "class_of_business": "tavern", "requested_limits": policy["limits"], "total_insured_value": 300000,
        "brokerage_id": a_brokerage(db), "broker_contact": "Dana Whitcomb", "renewal_of": policy["id"]})
    assert response.status_code == 409 and response.json()["code"] == "policy_lapsed"


def test_a_renewal_binds_only_while_the_expiring_term_is_in_force(make_client, db):
    policy = next_to_lapse(db)
    today = make_client()
    priya = sign_in(today, PRIYA)
    sub_id = new_submission(today, priya, db, renewal_of=policy["id"])
    today.post(f"/submissions/{sub_id}/decide", headers=priya, json={"action": "quote", "premium": 7000,
                                                                       "deductible": 1000})
    later = make_client(clock=on(policy["expires"]))
    response = later.post(f"/submissions/{sub_id}/decide", headers=sign_in(later, PRIYA), json={"action": "bind"})
    assert response.status_code == 409 and response.json()["code"] == "policy_lapsed"
    assert status_of(db, "submissions", sub_id) == "quoted"
    assert db.execute("SELECT count(*) FROM policies WHERE prior_policy_id = ?", (policy["id"],)).fetchone()[0] == 0


def test_a_senior_cancels_a_policy_inside_its_term(client, db):
    policy = a_cancellable_policy(db)
    body = {"cancelled_on": TODAY.isoformat(), "reason": "Insured closed the restaurant."}
    refused = client.post(f"/policies/{policy['id']}/cancel", headers=sign_in(client, PRIYA), json=body)
    assert refused.status_code == 403
    margit = sign_in(client, MARGIT)
    for day, code in (((TODAY + timedelta(days=1)).isoformat(), "future_date"),
                      ((datetime.fromisoformat(policy["effective"]) - timedelta(days=1)).date().isoformat(),
                       "outside_term")):
        response = client.post(f"/policies/{policy['id']}/cancel", headers=margit, json={**body, "cancelled_on": day})
        assert response.status_code == 422 and response.json()["code"] == code
    cancelled = client.post(f"/policies/{policy['id']}/cancel", headers=margit, json=body)
    assert cancelled.status_code == 200, cancelled.text
    assert (cancelled.json()["status"], cancelled.json()["cancelled_on"]) == ("cancelled", TODAY.isoformat())
    entry, = entries(db, "policy_cancelled")
    assert (entry["actor"], entry["policy_id"]) == (staff_id(db, MARGIT), policy["id"])
    again = client.post(f"/policies/{policy['id']}/cancel", headers=margit, json=body)
    assert again.status_code == 409 and again.json()["code"] == "policy_not_in_force"


def test_a_cancellation_comes_after_every_loss(client, db):
    claim = db.execute("SELECT c.policy_id, c.date_of_loss FROM claims c JOIN policies p ON p.id = c.policy_id "
                       "WHERE p.status = 'in_force' ORDER BY c.date_of_loss DESC LIMIT 1").fetchone()
    response = client.post(f"/policies/{claim['policy_id']}/cancel", headers=sign_in(client, MARGIT),
                           json={"cancelled_on": claim["date_of_loss"], "reason": "Nonpayment."})
    assert response.status_code == 422 and response.json()["code"] == "loss_on_or_after_cancellation"


def test_a_senior_closes_a_claim_without_lowering_what_was_paid(client, db):
    claim = db.execute("SELECT * FROM claims WHERE status = 'open' AND paid > 0 ORDER BY id LIMIT 1").fetchone()
    assert client.post(f"/claims/{claim['id']}/close", headers=sign_in(client, PRIYA),
                       json={"paid": claim["paid"]}).status_code == 403
    calvin = sign_in(client, CALVIN)
    lower = client.post(f"/claims/{claim['id']}/close", headers=calvin, json={"paid": claim["paid"] - 1})
    assert lower.status_code == 422 and lower.json()["code"] == "paid_lowered"
    closed = client.post(f"/claims/{claim['id']}/close", headers=calvin, json={"paid": claim["paid"] + 500})
    assert closed.status_code == 200
    assert (closed.json()["status"], closed.json()["paid"], closed.json()["reserve"]) == (
        "closed", claim["paid"] + 500, 0)
    assert entries(db, "claim_closed")[0]["claim_id"] == claim["id"]
    again = client.post(f"/claims/{claim['id']}/close", headers=calvin, json={"paid": claim["paid"] + 500})
    assert again.status_code == 409 and again.json()["code"] == "claim_closed"


def test_a_senior_sets_a_brokerage_inactive_and_it_sends_no_more_submissions(client, db):
    brokerage_id = a_brokerage(db)
    assert client.post(f"/brokerages/{brokerage_id}/status", headers=sign_in(client, PRIYA),
                       json={"status": "inactive"}).status_code == 403
    margit = sign_in(client, MARGIT)
    response = client.post(f"/brokerages/{brokerage_id}/status", headers=margit, json={"status": "inactive"})
    assert response.status_code == 200 and response.json()["status"] == "inactive"
    assert entries(db, "brokerage_status")[-1]["brokerage_id"] == brokerage_id
    same = client.post(f"/brokerages/{brokerage_id}/status", headers=margit, json={"status": "inactive"})
    assert same.status_code == 409 and same.json()["code"] == "status_unchanged"
    refused = client.post("/submissions", headers=sign_in(client, PRIYA), json={
        "business": "X LLC", "state": "IA", "address": "1 Elm St", "class_of_business": "tavern",
        "requested_limits": "GL $1M/$2M", "total_insured_value": 100000, "brokerage_id": brokerage_id,
        "broker_contact": "Dana"})
    assert refused.status_code == 422 and refused.json()["code"] == "brokerage_inactive"
    assert client.post(f"/brokerages/{brokerage_id}/status", headers=margit,
                       json={"status": "active"}).json()["status"] == "active"


def test_unknown_policy_claim_and_brokerage_are_404(client):
    margit = sign_in(client, MARGIT)
    for path, body in (("/policies/99999/cancel", {"cancelled_on": "2026-09-01", "reason": "x"}),
                       ("/claims/99999/close", {"paid": 0}), ("/brokerages/99999/status", {"status": "active"})):
        assert client.post(path, headers=margit, json=body).status_code == 404, path



def test_a_pending_policy_is_cancelled_flat(client, db):
    policy = db.execute("SELECT * FROM policies WHERE status = 'pending' ORDER BY id LIMIT 1").fetchone()
    margit = sign_in(client, MARGIT)
    later = (datetime.fromisoformat(policy["effective"]) + timedelta(days=5)).date().isoformat()
    refused = client.post(f"/policies/{policy['id']}/cancel", headers=margit,
                          json={"cancelled_on": later, "reason": "Insured sold the business."})
    assert refused.status_code == 422 and refused.json()["code"] == "flat_cancellation_only"
    cancelled = client.post(f"/policies/{policy['id']}/cancel", headers=margit,
                            json={"cancelled_on": policy["effective"], "reason": "Insured sold the business."})
    assert cancelled.status_code == 200, cancelled.text
    assert (cancelled.json()["status"], cancelled.json()["cancelled_on"]) == ("cancelled", policy["effective"])
