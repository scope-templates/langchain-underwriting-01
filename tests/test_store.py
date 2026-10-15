import sqlite3

import pytest

from app.db import MIGRATIONS, connect, init_db
from tests.conftest import (CALVIN, GRETCHEN, MARGIT, PRIYA, a_brokerage, a_renewable_policy, a_submission,
                            new_submission, sign_in, staff_id)

MOMENT = "'2026-10-01T10:00:00'"


def insert_decision(db, sub_id, actor, action, premium=None, deductible=None, at=MOMENT):
    db.execute("INSERT INTO decisions (actor, submission_id, action, premium, deductible, at) "
               f"VALUES (?, ?, ?, ?, ?, {at})", (actor, sub_id, action, premium, deductible))


def a_policy(db, status="in_force"):
    return db.execute("SELECT * FROM policies WHERE status = ? ORDER BY id LIMIT 1", (status,)).fetchone()


def insert_claim(db, policy_id, date_of_loss, reported_on=None):
    db.execute("INSERT INTO claims (policy_id, date_of_loss, reported_on, kind, paid, reserve, status) "
               "VALUES (?, ?, ?, 'theft', 0, 1500, 'open')", (policy_id, date_of_loss, reported_on or date_of_loss))


@pytest.mark.parametrize("table", ["decisions", "activity"])
def test_append_only_tables_refuse_update_delete_and_replace(db, table):
    sub_id = a_submission(db)
    if table == "activity":
        db.execute(f"INSERT INTO activity (actor, action, submission_id, detail, at) "
                   f"VALUES (3, 'scope_refused', ?, 'x', {MOMENT})", (sub_id,))
        db.commit()
    row_id = db.execute(f"SELECT max(id) FROM {table}").fetchone()[0]
    for sql in (f"UPDATE {table} SET at = {MOMENT} WHERE id = {row_id}", f"DELETE FROM {table} WHERE id = {row_id}"):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute(sql)
    if table == "activity":
        sql = (f"INSERT OR REPLACE INTO activity (id, actor, action, submission_id, detail, at) "
               f"VALUES ({row_id}, 3, 'scope_refused', {sub_id}, 'x', {MOMENT})")
    else:
        sql = (f"INSERT OR REPLACE INTO decisions (id, actor, action, submission_id, at) "
               f"VALUES ({row_id}, 3, 'decline', {sub_id}, {MOMENT})")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.execute(sql)


@pytest.mark.parametrize("table", ["brokerages", "policies", "submissions", "inspections_and_calls", "facts", "notes",
                                   "claims"])
def test_history_rows_cannot_be_replaced(db, table):
    undecided = " WHERE status = 'open'" if table == "submissions" else ""
    row = db.execute(f"SELECT * FROM {table}{undecided} ORDER BY id LIMIT 1").fetchone()
    columns = list(row.keys())
    with pytest.raises(sqlite3.IntegrityError, match="cannot be replaced"):
        db.execute(f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                   tuple(row))


def test_decision_entry_needs_a_staff_actor_with_the_role(db):
    sub_id = a_submission(db)
    for actor in (None, 999, staff_id(db, GRETCHEN)):
        with pytest.raises(sqlite3.IntegrityError):
            insert_decision(db, sub_id, actor, "decline")


def test_decision_entry_must_match_the_submission_status(db):
    priya, margit = staff_id(db, PRIYA), staff_id(db, MARGIT)
    for status, action in (("bound", "quote"), ("bound", "decline"), ("declined", "bind"), ("not_taken", "bind"),
                           ("open", "confirm"), ("open", "bind"), ("open", "not_taken"), ("quoted", "decline"),
                           ("quoted", "quote")):
        actor = margit if action == "confirm" else priya
        with pytest.raises(sqlite3.IntegrityError, match="match the submission status"):
            insert_decision(db, a_submission(db, status), actor, action, 5000, 1000)


def test_quote_entry_needs_a_premium_and_deductible(db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_decision(db, a_submission(db), staff_id(db, PRIYA), "quote", 5000, None)


def test_confirm_entry_by_the_quoter_or_an_underwriter_is_refused(client, db):
    margit = sign_in(client, MARGIT)
    sub_id = new_submission(client, margit, db)
    client.post(f"/submissions/{sub_id}/decide", headers=margit,
                json={"action": "quote", "premium": 26000, "deductible": 2500})
    for actor in (staff_id(db, MARGIT), staff_id(db, PRIYA)):
        with pytest.raises(sqlite3.IntegrityError, match="cannot take this decision"):
            insert_decision(db, sub_id, actor, "confirm", 26000, 2500, "'2026-10-01T11:00:00'")


def test_status_change_without_a_decision_entry_is_refused(db):
    for status in ("quoted", "declined", "referred"):
        with pytest.raises(sqlite3.IntegrityError, match="matching decision entry"):
            db.execute("UPDATE submissions SET status = ? WHERE id = ?", (status, a_submission(db)))
    with pytest.raises(sqlite3.IntegrityError, match="matching decision entry"):
        db.execute("UPDATE submissions SET status = 'bound' WHERE id = ?", (a_submission(db, "quoted"),))


@pytest.mark.parametrize("premium, value, refused", [(20_001, 400_000, "quoted"), (19_000, 5_000_001, "quoted"),
                                                     (19_000, 400_000, "referred")])
def test_quotes_above_authority_are_referred_and_within_it_are_not(client, db, premium, value, refused):
    sub_id = new_submission(client, sign_in(client, PRIYA), db, total_insured_value=value)
    insert_decision(db, sub_id, staff_id(db, PRIYA), "quote", premium, 1000)
    with pytest.raises(sqlite3.IntegrityError, match="matching decision entry"):
        db.execute("UPDATE submissions SET status = ? WHERE id = ?", (refused, sub_id))


def test_referred_quote_becomes_quoted_only_with_a_confirm_entry(client, db):
    priya = sign_in(client, PRIYA)
    sub_id = new_submission(client, priya, db)
    client.post(f"/submissions/{sub_id}/decide", headers=priya,
                json={"action": "quote", "premium": 24000, "deductible": 2500})
    with pytest.raises(sqlite3.IntegrityError, match="matching decision entry"):
        db.execute("UPDATE submissions SET status = 'quoted' WHERE id = ?", (sub_id,))


def test_open_submission_quote_changes_only_with_a_matching_entry(db):
    sub_id = a_submission(db)
    for column, value in (("annual_premium", 9999), ("deductible", 500), ("terms", "'none'"),
                          ("decided_by", staff_id(db, PRIYA)), ("decided_on", "'2026-10-01'")):
        with pytest.raises(sqlite3.IntegrityError, match="matching decision entry"):
            db.execute(f"UPDATE submissions SET {column} = {value} WHERE id = ?", (sub_id,))


def test_decided_submission_keeps_its_quote(db):
    for status in ("quoted", "bound", "declined", "not_taken"):
        sub_id = a_submission(db, status)
        for column, value in (("annual_premium", 99999), ("deductible", 500), ("decided_by", staff_id(db, CALVIN))):
            with pytest.raises(sqlite3.IntegrityError, match="keeps its premium"):
                db.execute(f"UPDATE submissions SET {column} = {value} WHERE id = ?", (sub_id,))


def test_submission_cannot_be_inserted_already_decided(db):
    with pytest.raises(sqlite3.IntegrityError, match="starts open"):
        db.execute("INSERT INTO submissions (business, state, address, class_of_business, requested_limits, "
                   "total_insured_value, brokerage_id, broker_contact, received_on, entered_by, status, decided_by, "
                   "decided_on, annual_premium, deductible) VALUES ('X LLC', 'IA', '1 Elm St', 'tavern', 'GL $1M/$2M', "
                   "100000, ?, 'Dana', '2026-09-01', 3, 'quoted', 3, '2026-09-01', 5000, 1000)", (a_brokerage(db),))


def test_submission_comes_from_an_active_brokerage(db):
    with pytest.raises(sqlite3.IntegrityError, match="active brokerage"):
        db.execute("INSERT INTO submissions (business, state, address, class_of_business, requested_limits, "
                   "total_insured_value, brokerage_id, broker_contact, received_on, entered_by) VALUES "
                   "('X LLC', 'IA', '1 Elm St', 'tavern', 'GL $1M/$2M', 100000, ?, 'Dana', '2026-09-01', 3)",
                   (a_brokerage(db, "inactive"),))


def test_submission_keeps_its_insured_value_and_renewal_link(db):
    sub_id = a_submission(db, "bound", renewal=True)
    for column, value in (("total_insured_value", 1), ("renewal_of", "NULL")):
        with pytest.raises(sqlite3.IntegrityError, match="keeps its insured value"):
            db.execute(f"UPDATE submissions SET {column} = {value} WHERE id = ?", (sub_id,))


def test_fact_row_needs_checked_on_and_checked_by(db):
    sub_id = a_submission(db)
    for checked_on, checked_by in (("'2026-09-01'", "NULL"), ("NULL", "3"), ("'2026-09-01'", "999")):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(f"INSERT INTO facts (submission_id, field, value, checked_on, checked_by) "
                       f"VALUES (?, 'owner', 'x', {checked_on}, {checked_by})", (sub_id,))


@pytest.mark.parametrize("value", ["''", "'2099-01-01'", "'2026-02-30'", "'09/01/2026'", "'1970-01-01'"])
def test_dates_must_be_iso_and_in_range(db, value):
    sub_id = a_submission(db)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute(f"INSERT INTO facts (submission_id, field, value, checked_on, checked_by) "
                   f"VALUES (?, 'owner', 'x', {value}, 3)", (sub_id,))
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute(f"INSERT INTO inspections_and_calls (submission_id, kind, with_whom, held_on, recorded_by, "
                   f"findings) VALUES (?, 'broker_call', 'X', {value}, 3, 'x')", (sub_id,))


@pytest.mark.parametrize("value", ["''", "'2099-01-01T10:00:00'", "'yesterday'"])
def test_timestamps_must_be_iso_and_in_range(db, value):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute(f"INSERT INTO notes (submission_id, author, written_at, body) VALUES (?, 3, {value}, 'x')",
                   (a_submission(db),))


def test_policy_leaves_in_force_once(db):
    for status in ("expired", "non_renewed", "cancelled"):
        policy = a_policy(db, status)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE policies SET status = 'in_force', cancelled_on = NULL WHERE id = ?", (policy["id"],))


def test_written_policy_keeps_its_terms(db):
    policy = a_policy(db)
    other_carrier = ("CASE carrier WHEN 'Coteau Casualty Company' THEN 'Callander Indemnity Company' "
                     "ELSE 'Coteau Casualty Company' END")
    for column, value in (("annual_premium", 1), ("expires", "'2030-01-01'"), ("carrier", other_carrier),
                          ("insured", "'Someone Else LLC'")):
        with pytest.raises(sqlite3.IntegrityError, match="keeps its terms"):
            db.execute(f"UPDATE policies SET {column} = {value} WHERE id = ?", (policy["id"],))


def test_renewal_term_starts_the_day_the_prior_term_expires(db):
    prior = a_policy(db)
    with pytest.raises(sqlite3.IntegrityError, match="prior term expires"):
        db.execute("INSERT INTO policies (insured, state, carrier, brokerage_id, effective, expires, annual_premium, "
                   "limits, status, prior_policy_id) VALUES (?, ?, ?, ?, date(?, '+3 days'), date(?, '+1 year'), "
                   "5000, 'GL $1M/$2M', 'in_force', ?)",
                   (prior["insured"], prior["state"], prior["carrier"], prior["brokerage_id"], prior["expires"],
                    prior["expires"], prior["id"]))


def test_claim_date_of_loss_falls_inside_the_term(db):
    policy = a_policy(db, "expired")
    outside = [db.execute("SELECT date(?, '-1 day')", (policy["effective"],)).fetchone()[0], policy["expires"]]
    for date_of_loss in outside:
        with pytest.raises(sqlite3.IntegrityError, match="inside its policy"):
            insert_claim(db, policy["id"], date_of_loss)
    insert_claim(db, policy["id"], policy["effective"])


def test_claim_on_a_cancelled_policy_falls_before_the_cancellation(db):
    policy = a_policy(db, "cancelled")
    with pytest.raises(sqlite3.IntegrityError, match="inside its policy"):
        insert_claim(db, policy["id"], policy["cancelled_on"])


def test_claim_is_reported_after_the_loss_and_closed_claims_hold_no_reserve(db):
    policy = a_policy(db, "expired")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert_claim(db, policy["id"], policy["effective"], "2001-01-01")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute("INSERT INTO claims (policy_id, date_of_loss, reported_on, kind, paid, reserve, status) "
                   "VALUES (?, ?, ?, 'theft', 0, 100, 'closed')",
                   (policy["id"], policy["effective"], policy["effective"]))


def policy_entry(db, policy_id, action, at):
    db.execute("INSERT INTO activity (actor, action, policy_id, detail, at) VALUES (3, ?, ?, 'x', ?)",
               (action, policy_id, at))


@pytest.mark.parametrize("table", ["inspections_and_calls", "facts", "notes"])
def test_desk_records_are_kept_as_written(db, table):
    row_id = db.execute(f"SELECT min(id) FROM {table}").fetchone()[0]
    for sql in (f"UPDATE {table} SET submission_id = submission_id WHERE id = ?", f"DELETE FROM {table} WHERE id = ?"):
        with pytest.raises(sqlite3.IntegrityError, match="kept as written"):
            db.execute(sql, (row_id,))


def test_closed_submissions_keep_their_details(db):
    for status in ("bound", "declined", "not_taken"):
        sub_id = a_submission(db, status)
        for column, value in (("business", "'Other LLC'"), ("address", "'1 Elm St'"), ("received_on", "'2026-01-05'")):
            with pytest.raises(sqlite3.IntegrityError, match="keeps its details"):
                db.execute(f"UPDATE submissions SET {column} = {value} WHERE id = ?", (sub_id,))
    db.execute("UPDATE submissions SET broker_contact = 'Dana Whitcomb' WHERE id = ?", (a_submission(db),))


def test_policy_status_change_needs_its_entry(db):
    policy_id = db.execute("SELECT id FROM policies p WHERE status = 'in_force' AND NOT EXISTS "
                           "(SELECT 1 FROM claims c WHERE c.policy_id = p.id) ORDER BY id LIMIT 1").fetchone()[0]
    for status in ("expired", "non_renewed", "cancelled", "pending"):
        with pytest.raises(sqlite3.IntegrityError, match="follows its dates"):
            db.execute("UPDATE policies SET status = ?, cancelled_on = CASE ? WHEN 'cancelled' THEN effective END "
                       "WHERE id = ?", (status, status, policy_id))


def test_a_term_ends_only_on_its_expiry_date_and_with_the_status_it_has_earned(db):
    policy = db.execute("SELECT * FROM policies WHERE id = ?", (a_renewable_policy(db),)).fetchone()
    policy_entry(db, policy["id"], "policy_ended", "2026-10-01T09:00:00")
    with pytest.raises(sqlite3.IntegrityError, match="follows its dates"):
        db.execute("UPDATE policies SET status = 'expired' WHERE id = ?", (policy["id"],))
    policy_entry(db, policy["id"], "policy_ended", f"{policy['expires']}T09:00:00")
    with pytest.raises(sqlite3.IntegrityError, match="follows its dates"):
        db.execute("UPDATE policies SET status = 'non_renewed' WHERE id = ?", (policy["id"],))
    db.execute("UPDATE policies SET status = 'expired' WHERE id = ?", (policy["id"],))


def test_a_term_with_its_renewal_declined_ends_non_renewed(db):
    sub = db.execute("SELECT s.renewal_of, p.expires FROM submissions s JOIN policies p ON p.id = s.renewal_of "
                     "WHERE s.status IN ('declined', 'not_taken') AND p.status = 'in_force' ORDER BY s.id LIMIT 1"
                     ).fetchone()
    policy_entry(db, sub["renewal_of"], "policy_ended", f"{sub['expires']}T08:30:00")
    with pytest.raises(sqlite3.IntegrityError, match="follows its dates"):
        db.execute("UPDATE policies SET status = 'expired' WHERE id = ?", (sub["renewal_of"],))
    db.execute("UPDATE policies SET status = 'non_renewed' WHERE id = ?", (sub["renewal_of"],))


def test_a_pending_term_starts_on_its_effective_date_or_is_cancelled_flat(db):
    policy = db.execute("SELECT * FROM policies WHERE status = 'pending' ORDER BY id LIMIT 1").fetchone()
    policy_entry(db, policy["id"], "policy_started", "2026-10-01T09:00:00")
    with pytest.raises(sqlite3.IntegrityError, match="follows its dates"):
        db.execute("UPDATE policies SET status = 'in_force' WHERE id = ?", (policy["id"],))
    policy_entry(db, policy["id"], "policy_cancelled", "2026-10-01T09:05:00")
    with pytest.raises(sqlite3.IntegrityError, match="cancelled flat"):
        db.execute("UPDATE policies SET status = 'cancelled', cancelled_on = date(effective, '+1 day') WHERE id = ?",
                   (policy["id"],))
    db.execute("UPDATE policies SET status = 'cancelled', cancelled_on = effective WHERE id = ?", (policy["id"],))


def test_cancellation_comes_after_every_loss_and_is_set_once(db):
    claim = db.execute("SELECT c.policy_id, c.date_of_loss FROM claims c JOIN policies p ON p.id = c.policy_id "
                       "WHERE p.status = 'in_force' ORDER BY c.id LIMIT 1").fetchone()
    db.execute("INSERT INTO activity (actor, action, policy_id, detail, at) "
               "VALUES (1, 'policy_cancelled', ?, 'x', '2026-10-01T09:00:00')", (claim["policy_id"],))
    with pytest.raises(sqlite3.IntegrityError, match="after every loss"):
        db.execute("UPDATE policies SET status = 'cancelled', cancelled_on = ? WHERE id = ?",
                   (claim["date_of_loss"], claim["policy_id"]))
    cancelled = a_policy(db, "cancelled")
    with pytest.raises(sqlite3.IntegrityError, match="set once"):
        db.execute("UPDATE policies SET cancelled_on = date(cancelled_on, '+1 day') WHERE id = ?", (cancelled["id"],))


def test_one_open_renewal_and_one_renewal_term_per_policy(client, db):
    priya = sign_in(client, PRIYA)
    policy_id = a_renewable_policy(db)
    new_submission(client, priya, db, renewal_of=policy_id)
    row = db.execute("SELECT * FROM submissions WHERE renewal_of = ?", (policy_id,)).fetchone()
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        db.execute("INSERT INTO submissions (business, state, address, class_of_business, requested_limits, "
                   "total_insured_value, brokerage_id, broker_contact, received_on, entered_by, renewal_of) "
                   "VALUES ('X LLC', 'IA', '1 Elm St', 'tavern', 'GL', 1000, ?, 'Dana', '2026-09-30', 3, ?)",
                   (row["brokerage_id"], policy_id))
    renewed = db.execute("SELECT * FROM policies WHERE id = (SELECT prior_policy_id FROM policies "
                         "WHERE prior_policy_id IS NOT NULL ORDER BY id LIMIT 1)").fetchone()
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        db.execute("INSERT INTO policies (insured, state, carrier, brokerage_id, effective, expires, annual_premium, "
                   "limits, status, prior_policy_id) VALUES (?, ?, ?, ?, ?, date(?, '+1 year'), 5000, 'GL', "
                   "'in_force', ?)", (renewed["insured"], renewed["state"], renewed["carrier"],
                                      renewed["brokerage_id"], renewed["expires"], renewed["expires"], renewed["id"]))


def test_claims_move_only_forward(db):
    open_claim = db.execute("SELECT * FROM claims WHERE status = 'open' AND paid > 0 ORDER BY id LIMIT 1").fetchone()
    closed = db.execute("SELECT id FROM claims WHERE status = 'closed' ORDER BY id LIMIT 1").fetchone()["id"]
    for sql, args in (("UPDATE claims SET paid = paid - 10 WHERE id = ?", (open_claim["id"],)),
                      ("UPDATE claims SET date_of_loss = date(date_of_loss, '+1 day') WHERE id = ?",
                       (open_claim["id"],)),
                      ("UPDATE claims SET status = 'open', reserve = 100 WHERE id = ?", (closed,)),
                      ("UPDATE claims SET paid = paid + 10 WHERE id = ?", (closed,)),
                      ("DELETE FROM claims WHERE id = ?", (closed,))):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql, args)
    db.execute("UPDATE claims SET paid = paid + 10, reserve = reserve WHERE id = ?", (open_claim["id"],))


def test_brokerage_status_change_needs_its_entry(db):
    brokerage_id = a_brokerage(db)
    with pytest.raises(sqlite3.IntegrityError, match="entry in activity"):
        db.execute("UPDATE brokerages SET status = 'inactive' WHERE id = ?", (brokerage_id,))
    db.execute("INSERT INTO activity (actor, action, brokerage_id, detail, at) "
               "VALUES (1, 'brokerage_status', ?, 'inactive', '2026-10-01T09:00:00')", (brokerage_id,))
    db.execute("UPDATE brokerages SET status = 'inactive' WHERE id = ?", (brokerage_id,))


def test_activity_entries_name_their_subject(db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute("INSERT INTO activity (actor, action, policy_id, detail, at) "
                   "VALUES (1, 'save_note', 1, 'x', '2026-10-01T09:00:00')")


def test_store_carries_the_schema_version(db):
    assert db.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_a_store_at_an_earlier_version_is_migrated_with_its_rows(tmp_path):
    path = tmp_path / "older.db"
    conn = connect(path)
    for number, (_, sql) in enumerate(MIGRATIONS[:2], start=1):
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    with conn:
        conn.execute("INSERT INTO staff (id, name, email, role) VALUES (1, 'Pat Doe', 'pat@x.test', 'underwriter')")
        conn.execute("INSERT INTO brokerages (id, name, city, state, appointed_on, status) "
                     "VALUES (1, 'Doe Insurance', 'Ardmoor', 'IL', '2023-01-02', 'active')")
        conn.execute("INSERT INTO submissions (id, business, state, address, class_of_business, requested_limits, "
                     "total_insured_value, brokerage_id, broker_contact, received_on, entered_by) VALUES "
                     "(1, 'X LLC', 'IL', '1 Elm St', 'tavern', 'GL', 1000, 1, 'Dana', '2026-03-02', 1)")
        conn.execute("INSERT INTO activity (id, actor, action, submission_id, detail, at) "
                     "VALUES (7, 1, 'save_note', 1, 'note 1', '2026-03-02T10:00:00')")
    conn.close()
    init_db(path)
    conn = connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
    assert tuple(conn.execute("SELECT id, action, submission_id, policy_id FROM activity").fetchone()) == (
        7, "save_note", 1, None)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM activity")
    conn.close()
