import itertools
import json
import sqlite3
import threading
import time
from datetime import date, timedelta

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel

import app.assistant.loop as loop
import app.submissions
from app.assistant.model import build_model
from tests.conftest import NOW, PRIYA, a_submission, other_submission, sign_in, staff_id
from tests.fake_model import FakeChatModel, PayloadRecordingOpenAI, tool_call, tool_name

DESK_TOOLS = {
    "submission_summary": {},
    "inspections": {},
    "facts": {},
    "loss_history": {},
    "save_note": {"body": "Broker says the patio opens in May."},
}


def ask(client, sub_id, question="What did the inspection find?"):
    return client.post(f"/assistant/submissions/{sub_id}", headers=sign_in(client, PRIYA),
                       json={"question": question})


def tool_messages(model, call_index):
    return [m for m in model.calls[call_index] if isinstance(m, ToolMessage)]


def scripted(*calls, answer="Here is what the desk holds.") -> FakeChatModel:
    replies = [AIMessage(content="", tool_calls=[c]) for c in calls]
    return FakeChatModel(replies=replies + [AIMessage(content=answer)])


def activity(db, action):
    return db.execute("SELECT actor, submission_id, detail FROM activity WHERE action = ? ORDER BY id",
                      (action,)).fetchall()


def test_unset_key_closes_only_the_assistant(make_client, db, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = make_client(model_factory=build_model)
    sub_id = a_submission(db)
    response = ask(client, sub_id)
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "assistant_unconfigured"

    headers = sign_in(client, PRIYA)
    for path in ("/submissions", f"/submissions/{sub_id}", "/brokerages", "/policies", "/policies/1/losses"):
        assert client.get(path, headers=headers).status_code == 200, path
    assert client.post(f"/submissions/{sub_id}/notes", headers=headers, json={"body": "Called."}).status_code == 201


@pytest.mark.parametrize("value", ["", "   ", "changeme", "<your key>", "sk-...", "your-openai-key", "xxxx", "${KEY}"])
def test_placeholder_keys_count_as_unset(monkeypatch, value):
    monkeypatch.setenv("OPENAI_API_KEY", value)
    assert build_model() is None


def test_a_key_builds_a_model_without_calling_it(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-4f7c2e9a")
    assert build_model() is not None


def test_answer_carries_text_and_tool_calls(make_client, db):
    sub_id = a_submission(db, "bound", renewal=True)
    model = scripted(tool_call("loss_history", submission_id=sub_id), answer="One slip and fall, closed.")
    response = ask(make_client(model), sub_id)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "answer": "One slip and fall, closed.",
        "tool_calls": [{"name": "loss_history", "args": {"submission_id": sub_id}}],
    }
    result = json.loads(tool_messages(model, 1)[0].content)
    expiring = db.execute("SELECT renewal_of FROM submissions WHERE id = ?", (sub_id,)).fetchone()[0]
    assert result["expiring_policy"] == expiring and result["terms"][0]["id"] == expiring


def test_loss_history_is_empty_for_new_business(make_client, db):
    sub_id = a_submission(db, renewal=False)
    model = scripted(tool_call("loss_history", submission_id=sub_id))
    ask(make_client(model), sub_id)
    assert json.loads(tool_messages(model, 1)[0].content) == {"expiring_policy": None}


@pytest.mark.parametrize("name", DESK_TOOLS)
def test_each_desk_tool_is_bound_and_scoped_to_the_path(make_client, db, name):
    sub_id = a_submission(db)
    other = other_submission(db, sub_id)
    model = scripted(tool_call(name, submission_id=other, **DESK_TOOLS[name]),
                     tool_call(name, call_id="call_2", submission_id=sub_id, **DESK_TOOLS[name]))
    response = ask(make_client(model), sub_id)
    assert name in model.binds[0]["tools"]
    assert response.json()["tool_calls"] == [{"name": name, "args": {"submission_id": sub_id, **DESK_TOOLS[name]}}]
    refusal, = tool_messages(model, 1)
    assert refusal.status == "error" and "Refused" in refusal.content
    assert tool_messages(model, 2)[-1].status != "error"
    assert [tuple(r)[:2] for r in activity(db, "scope_refused")] == [(staff_id(db, PRIYA), sub_id)]


def test_numeric_string_ids_are_read_and_other_shapes_refused(make_client, db):
    sub_id = a_submission(db)
    model = scripted(tool_call("inspections", submission_id=str(sub_id)),
                     tool_call("inspections", call_id="call_2", submission_id=f"{sub_id}a"),
                     tool_call("inspections", call_id="call_3", submission_id=float(sub_id)),
                     tool_call("inspections", call_id="call_4", submission_id=True))
    response = ask(make_client(model), sub_id)
    assert len(response.json()["tool_calls"]) == 1
    assert len(activity(db, "scope_refused")) == 3


def test_loop_stops_at_six_model_calls_with_tools_off_for_the_last(make_client, db):
    sub_id = a_submission(db)
    model = FakeChatModel(replies=[
        AIMessage(content="Reading the inspection.", tool_calls=[tool_call("inspections", submission_id=sub_id)]),
    ])
    response = ask(make_client(model), sub_id)
    assert response.status_code == 200
    assert len(model.calls) == loop.MAX_MODEL_CALLS == 6
    assert response.json()["answer"] == "Reading the inspection."
    assert len(response.json()["tool_calls"]) == loop.MAX_MODEL_CALLS - 1
    assert model.call_binds[-1].get("tool_choice") == "none"
    assert model.call_binds[-1]["tools"] == model.call_binds[0]["tools"]


def test_the_last_request_keeps_the_desk_tools_and_turns_tool_use_off(make_client, db):
    sub_id = a_submission(db)
    model = PayloadRecordingOpenAI(model="gpt-4.1-mini", api_key="sk-test", replies=[
        AIMessage(content="Checking the facts.", tool_calls=[tool_call("facts", submission_id=sub_id)]),
    ])
    response = ask(make_client(model), sub_id)
    assert response.status_code == 200 and len(model.payloads) == 6
    last = model.payloads[-1]
    assert last["tool_choice"] == "none"
    assert set(DESK_TOOLS) <= {tool_name(t) for t in last["tools"]}


def test_an_unnamed_tool_entry_is_bound_on_every_call_beside_the_desk_tools(make_client, db, monkeypatch):
    hosted = {"type": "hosted_lookup"}
    monkeypatch.setattr(loop, "TOOLS", [*loop.TOOLS, hosted])
    sub_id = a_submission(db)
    model = FakeChatModel(replies=[
        AIMessage(content="Reading the facts.", tool_calls=[tool_call("facts", submission_id=sub_id)]),
    ])
    response = ask(make_client(model), sub_id)
    assert response.status_code == 200 and response.json()["answer"] == "Reading the facts."
    assert len(model.calls) == loop.MAX_MODEL_CALLS
    assert all(hosted in bind["given"] for bind in model.call_binds)
    assert set(DESK_TOOLS) <= set(model.call_binds[-1]["tools"])


def test_unreadable_tool_calls_get_an_error_result(make_client, db):
    sub_id = a_submission(db)
    bad = {"name": "inspections", "args": "{submission_id: ", "id": "call_9", "error": "bad JSON",
           "type": "invalid_tool_call"}
    model = FakeChatModel(replies=[AIMessage(content="", invalid_tool_calls=[bad]),
                                   AIMessage(content="Here are the inspection findings.")])
    response = ask(make_client(model), sub_id)
    assert response.status_code == 200 and len(model.calls) == 2
    result, = tool_messages(model, 1)
    assert result.tool_call_id == "call_9" and result.status == "error"


def test_tool_calls_per_question_are_capped(make_client, db):
    sub_id = a_submission(db)
    calls = [tool_call("facts", call_id=f"call_{i}", submission_id=sub_id) for i in range(loop.MAX_TOOL_CALLS + 3)]
    model = FakeChatModel(replies=[AIMessage(content="", tool_calls=calls), AIMessage(content="Done reading.")])
    response = ask(make_client(model), sub_id)
    assert len(response.json()["tool_calls"]) == loop.MAX_TOOL_CALLS
    results = tool_messages(model, 1)
    assert len(results) == loop.MAX_TOOL_CALLS + 3
    assert [r.status for r in results[loop.MAX_TOOL_CALLS:]] == ["error"] * 3


def test_save_note_writes_once_under_the_signed_in_person(make_client, db):
    sub_id = a_submission(db)
    model = scripted(tool_call("save_note", submission_id=sub_id, body="Asked the broker for the menu again."),
                     tool_call("save_note", call_id="call_2", submission_id=sub_id, body="Second note."),
                     answer="Saved.")
    response = ask(make_client(model), sub_id, "Save a note that we asked for the menu again.")
    assert response.status_code == 200
    rows = db.execute("SELECT body, author FROM notes WHERE submission_id = ? AND written_at = ?",
                      (sub_id, "2026-10-01T10:00:00")).fetchall()
    assert [tuple(r) for r in rows] == [("Asked the broker for the menu again.", staff_id(db, PRIYA))]
    assert tool_messages(model, 2)[-1].status == "error"
    assert len(activity(db, "save_note")) == 1


@pytest.mark.parametrize("body", ["x" * 2001, "   "])
def test_save_note_refuses_long_or_blank_text(make_client, db, body):
    sub_id = a_submission(db)
    model = scripted(tool_call("save_note", submission_id=sub_id, body=body), answer="Not saved.")
    before = db.execute("SELECT count(*) FROM notes").fetchone()[0]
    ask(make_client(model), sub_id)
    assert tool_messages(model, 1)[0].status == "error"
    assert db.execute("SELECT count(*) FROM notes").fetchone()[0] == before


def test_model_failure_is_a_502_problem(make_client, db):
    model = FakeChatModel(replies=[TimeoutError("read timed out")])
    response = ask(make_client(model), a_submission(db))
    assert response.status_code == 502 and response.json()["code"] == "model_call_failed"


def test_failed_model_call_is_retried_once(make_client, db):
    model = FakeChatModel(replies=[TimeoutError("read timed out"), AIMessage(content="The inspection was clean.")])
    response = ask(make_client(model), a_submission(db))
    assert response.status_code == 200 and len(model.calls) == 2


class Clock:
    """Stands in for the loop's clock, in seconds."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def moves_to(self, seconds: float):
        return lambda: setattr(self, "now", seconds)


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(loop, "monotonic", clock)
    return clock


@pytest.fixture
def release():
    """Holds a slow tool until the test ends."""
    event = threading.Event()
    yield event
    event.set()


def adding_tool(**tools):
    """Adds `lookup` to the loop's tools; `tools[key]` runs when it is called with that key."""
    @tool
    def lookup(key: str) -> str:
        """Returns the value kept under a key."""
        tools.get(key, lambda: None)()
        return f"value for {key}"

    return [*loop.TOOLS, lookup]


def test_a_tool_that_runs_past_its_limit_gets_a_failed_result(make_client, db, monkeypatch, release):
    monkeypatch.setattr(loop, "TOOLS", adding_tool(slow=lambda: release.wait(10)))
    monkeypatch.setattr(loop, "TOOL_CALL_SECONDS", 0.05)
    model = scripted(tool_call("lookup", key="slow"), answer="The value did not come back.")
    response = ask(make_client(model), a_submission(db))
    assert response.status_code == 200 and len(model.calls) == 2
    result, = tool_messages(model, 1)
    assert result.status == "error" and "TimeoutError" in result.content
    failure, = activity(db, "tool_failed")
    assert failure["detail"].startswith("lookup:")


def test_a_tool_waits_no_longer_than_the_time_left_for_tools(make_client, db, monkeypatch, clock, release):
    tools_until = loop.QUESTION_DEADLINE_SECONDS - loop.FINAL_CALL_SECONDS
    monkeypatch.setattr(loop, "TOOLS", adding_tool(quick=clock.moves_to(tools_until - 0.05),
                                                   slow=lambda: release.wait(10)))
    call = tool_call("lookup", key="quick"), tool_call("lookup", call_id="call_2", key="slow")
    model = FakeChatModel(replies=[AIMessage(content="", tool_calls=list(call)), AIMessage(content="One value.")])
    response = ask(make_client(model), a_submission(db))
    assert response.status_code == 200
    quick, slow = tool_messages(model, 1)
    assert quick.content == "value for quick" and slow.status == "error" and "TimeoutError" in slow.content


def test_once_the_time_for_tools_is_up_the_tools_off_call_answers_with_the_finished_results(make_client, db,
                                                                                            monkeypatch, clock):
    sub_id = a_submission(db)
    monkeypatch.setattr(loop, "TOOLS", adding_tool(long=clock.moves_to(71)))
    calls = [tool_call("lookup", key="long"), tool_call("facts", call_id="call_2", submission_id=sub_id)]
    model = FakeChatModel(replies=[AIMessage(content="", tool_calls=calls), AIMessage(content="One value came back.")])
    response = ask(make_client(model), sub_id)
    assert response.status_code == 200, response.text
    assert response.json() == {"answer": "One value came back.",
                               "tool_calls": [{"name": "lookup", "args": {"key": "long"}}]}
    assert len(model.calls) == 2 and model.call_binds[-1].get("tool_choice") == "none"
    assert model.timeouts[-1] == min(loop.MODEL_CALL_SECONDS, loop.QUESTION_DEADLINE_SECONDS - 71)
    finished, unstarted = tool_messages(model, 1)
    assert finished.content == "value for long" and unstarted.status == "error"
    assert [r["detail"].split(":")[0] for r in activity(db, "tool_failed")] == ["facts"]


def test_a_retry_cut_off_by_the_time_for_tools_leaves_the_tools_off_call_to_answer(make_client, db,
                                                                                    monkeypatch, clock):
    monkeypatch.setattr(loop, "TOOLS", adding_tool(long=clock.moves_to(50)))

    def cut_off():
        clock.now = loop.QUESTION_DEADLINE_SECONDS - loop.FINAL_CALL_SECONDS
        raise TimeoutError("read timed out")

    model = FakeChatModel(replies=[AIMessage(content="", tool_calls=[tool_call("lookup", key="long")]),
                                   RuntimeError("server error"), cut_off, AIMessage(content="One value came back.")])
    response = ask(make_client(model), a_submission(db))
    assert response.status_code == 200, response.text
    assert response.json() == {"answer": "One value came back.",
                               "tool_calls": [{"name": "lookup", "args": {"key": "long"}}]}
    assert len(model.calls) == 4 and model.call_binds[-1].get("tool_choice") == "none"
    assert model.timeouts[2] == loop.QUESTION_DEADLINE_SECONDS - loop.FINAL_CALL_SECONDS - 50
    assert [m.content for m in tool_messages(model, 3)] == ["value for long"]


def test_no_model_call_starts_after_the_question_deadline(make_client, db, monkeypatch, clock):
    monkeypatch.setattr(loop, "TOOLS", adding_tool(long=clock.moves_to(91)))
    model = scripted(tool_call("lookup", key="long"))
    response = ask(make_client(model), a_submission(db))
    assert response.status_code == 502 and "deadline" in response.json()["detail"]
    assert len(model.calls) == 1


class Item(BaseModel):
    label: str


@pytest.mark.parametrize("result, text", [
    ("Zoë — déjà vu ✓", "Zoë — déjà vu ✓"),
    ({"label": "Zoë", "on": date(2019, 4, 1)}, '{"label": "Zoë", "on": "2019-04-01"}'),
    (Item(label="déjà vu – ok"), '{"label": "déjà vu – ok"}'),
    ([Item(label="déjà vu"), {"item": Item(label="ok")}], '[{"label": "déjà vu"}, {"item": {"label": "ok"}}]'),
], ids=["string", "dict", "pydantic", "pydantic inside a list"])
def test_tool_results_reach_the_model_as_text(make_client, db, monkeypatch, result, text):
    @tool
    def lookup() -> object:
        """Returns a value."""
        return result

    monkeypatch.setattr(loop, "TOOLS", [*loop.TOOLS, lookup])
    model = scripted(tool_call("lookup"))
    ask(make_client(model), a_submission(db))
    assert tool_messages(model, 1)[0].content == text


@pytest.mark.parametrize("doc", ["Returns the value kept under a key.", None])
def test_a_plain_function_in_the_tools_is_bound_and_run(make_client, db, monkeypatch, doc):
    def lookup(key: str) -> str:
        return f"value for {key}"

    lookup.__doc__ = doc
    monkeypatch.setattr(loop, "TOOLS", [*loop.TOOLS, lookup])
    model = scripted(tool_call("lookup", key="a"), answer="One value.")
    response = ask(make_client(model), a_submission(db))
    assert "lookup" in model.binds[0]["tools"]
    assert response.json()["tool_calls"] == [{"name": "lookup", "args": {"key": "a"}}]
    assert tool_messages(model, 1)[0].content == "value for a"
    assert activity(db, "tool_refused") == []


def test_a_bound_method_in_the_tools_is_bound_and_run(make_client, db, monkeypatch):
    class Table:
        def lookup(self, key: str) -> str:
            """Returns the value kept under a key."""
            return f"value for {key}"

    monkeypatch.setattr(loop, "TOOLS", [*loop.TOOLS, Table().lookup])
    model = scripted(tool_call("lookup", key="a"), answer="One value.")
    response = ask(make_client(model), a_submission(db))
    assert response.json()["tool_calls"] == [{"name": "lookup", "args": {"key": "a"}}]
    assert activity(db, "tool_refused") == []


def test_a_note_cut_off_by_its_limit_is_saved_with_its_activity_row_or_not_at_all(make_client, db, monkeypatch):
    insert, workers = app.submissions.insert_note, []

    def slow_insert(*args):
        workers.append(threading.current_thread())
        note = insert(*args)
        time.sleep(0.3)
        return note

    monkeypatch.setattr(app.submissions, "insert_note", slow_insert)
    monkeypatch.setattr(loop, "TOOL_CALL_SECONDS", 0.05)
    sub_id = a_submission(db)
    model = scripted(tool_call("save_note", submission_id=sub_id, body="Menu came in."),
                     tool_call("save_note", submission_id=sub_id, body="Menu came in again."), answer="Not saved.")
    response = ask(make_client(model), sub_id)
    for worker in workers:
        worker.join(5)
    assert response.status_code == 200
    failure, = activity(db, "tool_failed")
    assert failure["detail"].startswith("save_note:") and "TimeoutError" in failure["detail"]
    refused, = activity(db, "tool_refused")
    assert "already saved" in refused["detail"]
    notes = db.execute("SELECT count(*) FROM notes WHERE body IN ('Menu came in.', 'Menu came in again.')"
                       ).fetchone()[0]
    assert notes == len(activity(db, "save_note")) <= 1
    assert response.json()["tool_calls"] == []


@tool
def days_between(start: str, end: str) -> int:
    """Days from one ISO date to another."""
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def test_the_submission_scope_check_covers_the_desk_tools_only(make_client, db, monkeypatch):
    monkeypatch.setattr(loop, "TOOLS", [*loop.TOOLS, days_between])
    sub_id = a_submission(db)
    model = scripted(tool_call("days_between", start="2026-09-01", end="2026-10-01"), answer="Thirty days.")
    response = ask(make_client(model), sub_id)
    assert "days_between" in model.binds[0]["tools"]
    assert response.json()["tool_calls"] == [{"name": "days_between",
                                              "args": {"start": "2026-09-01", "end": "2026-10-01"}}]
    result, = tool_messages(model, 1)
    assert result.status != "error" and result.content == "30"
    assert activity(db, "scope_refused") == [] and activity(db, "tool_refused") == []


def test_a_desk_tool_call_without_an_id_reads_the_submission_in_the_path(make_client, db):
    sub_id = a_submission(db)
    model = scripted(tool_call("submission_summary"))
    response = ask(make_client(model), sub_id)
    assert response.json()["tool_calls"] == [{"name": "submission_summary", "args": {}}]
    assert json.loads(tool_messages(model, 1)[0].content)["id"] == sub_id


@pytest.mark.parametrize("asked", ["\uff11", "\u00b2", "\u0661\u0662"])
def test_ids_written_in_other_digit_sets_are_refused(make_client, db, asked):
    sub_id = a_submission(db)
    model = scripted(tool_call("facts", submission_id=asked))
    response = ask(make_client(model), sub_id)
    assert response.status_code == 200 and response.json()["tool_calls"] == []
    assert tool_messages(model, 1)[0].status == "error"
    assert len(activity(db, "scope_refused")) == 1


def test_refused_calls_are_recorded_in_activity(make_client, db):
    sub_id = a_submission(db)
    calls = [tool_call("no_such_tool", call_id="call_0")]
    calls += [tool_call("facts", call_id=f"call_{i}", submission_id=sub_id) for i in range(1, loop.MAX_TOOL_CALLS + 1)]
    model = FakeChatModel(replies=[AIMessage(content="", tool_calls=calls), AIMessage(content="Done.")])
    ask(make_client(model), sub_id)
    details = [r["detail"] for r in activity(db, "tool_refused")]
    assert len(details) == 2
    assert details[0].startswith("no_such_tool:") and "tool calls" in details[1]


def test_a_saved_note_is_stamped_when_it_is_written(make_client, db):
    seconds = itertools.count()
    client = make_client(scripted(tool_call("save_note", submission_id=a_submission(db), body="Menu came in.")),
                         clock=lambda: NOW + timedelta(seconds=next(seconds)))
    response = client.post(f"/assistant/submissions/{a_submission(db)}", headers=sign_in(client, PRIYA),
                           json={"question": "Note that the menu came in."})
    assert response.status_code == 200
    note = db.execute("SELECT written_at FROM notes WHERE body = 'Menu came in.'").fetchone()
    saved = db.execute("SELECT at FROM activity WHERE action = 'save_note'").fetchone()
    assert note["written_at"] == saved["at"] > NOW.isoformat()


def test_unexpected_tool_failure_is_an_error_result(make_client, db, monkeypatch):
    def broken(*args):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(app.submissions, "list_contacts", broken)
    sub_id = a_submission(db)
    model = scripted(tool_call("inspections", submission_id=sub_id), answer="The inspections did not load.")
    response = ask(make_client(model), sub_id)
    assert response.status_code == 200
    result, = tool_messages(model, 1)
    assert result.status == "error" and "OperationalError" in result.content
    failure, = activity(db, "tool_failed")
    assert failure["detail"].startswith("inspections:") and "OperationalError" in failure["detail"]


def test_submission_summary_carries_the_decision_entries(make_client, db):
    sub_id = a_submission(db, "bound")
    model = scripted(tool_call("submission_summary", submission_id=sub_id))
    ask(make_client(model), sub_id)
    summary = json.loads(tool_messages(model, 1)[0].content)
    actions = [d["action"] for d in summary["decisions"]]
    assert actions[0] == "quote" and actions[-1] == "bind"
    assert summary["policy_id"] is not None and all({"actor", "at"} <= set(d) for d in summary["decisions"])


def test_empty_answer_is_a_502_problem(make_client, db):
    response = ask(make_client(FakeChatModel(replies=[AIMessage(content="  ")])), a_submission(db))
    assert response.status_code == 502 and response.json()["code"] == "model_call_failed"


def test_question_past_its_deadline_is_a_502_problem(make_client, db, monkeypatch):
    monkeypatch.setattr(loop, "QUESTION_DEADLINE_SECONDS", -1)
    model = FakeChatModel(replies=[AIMessage(content="ok")])
    response = ask(make_client(model), a_submission(db))
    assert response.status_code == 502 and model.calls == []


def test_system_prompt_names_the_submission_asker_and_date(make_client, db):
    sub_id, *business = db.execute("SELECT id, business, dba, state FROM submissions WHERE dba IS NOT NULL "
                                   "ORDER BY id LIMIT 1").fetchone()
    model = FakeChatModel(replies=[AIMessage(content="ok")])
    ask(make_client(model), sub_id)
    prompt = model.calls[0][0].content
    assert f"number {sub_id}" in prompt and "Priya Ramaswamy" in prompt and "2026-10-01" in prompt
    assert all(value in prompt for value in business)


def test_unknown_submission_is_404_before_the_model(make_client):
    model = FakeChatModel(replies=[AIMessage(content="ok")])
    response = ask(make_client(model), 9999)
    assert response.status_code == 404 and model.calls == []
