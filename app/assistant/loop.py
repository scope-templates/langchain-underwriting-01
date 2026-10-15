import json
from dataclasses import dataclass, field
from time import monotonic

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from app.assistant.tools import SCOPED_TO_SUBMISSION, TOOLS, Desk, record_activity
from app.db import PREMIUM_AUTHORITY, VALUE_AUTHORITY
from app.problems import Problem

MAX_MODEL_CALLS = 6
MAX_TOOL_CALLS = 12
QUESTION_DEADLINE_SECONDS = 90
MODEL_CALL_SECONDS = 30
MODEL_ATTEMPTS = 2


def system_prompt(desk: Desk) -> str:
    return (
        "You answer questions for the Ketterly Underwriting desk. Ketterly is a managing general underwriter "
        "writing commercial package policies (general liability and property, with optional liquor liability) "
        "for independent restaurants, bars, caterers and small food producers in eight Midwest states, through "
        f"independent insurance brokerages. Every question is about one submission, number {desk.submission_id}, "
        f"and is asked by {desk.staff.name} ({desk.staff.role}). Today is {desk.clock().date().isoformat()}.\n\n"
        "Tools: submission_summary reads the submission, its brokerage, its notes and its decision entries; "
        "inspections reads the inspection reports and broker calls; facts reads the fact rows the desk holds on "
        "the business; loss_history reads the expiring policy and its claims when the submission is a renewal; "
        f"save_note saves a note on the submission under {desk.staff.name}'s name. Pass submission_id "
        f"{desk.submission_id} to each of these five.\n\n"
        "Underwriters quote, decline and bind through the desk's own routes. A quote with an annual premium over "
        f"${PREMIUM_AUTHORITY:,} or a total insured value over ${VALUE_AUTHORITY:,} is referred to a senior "
        "underwriter who did not quote it. Save a note only when asked to. Answer in plain sentences an "
        "underwriter can act on, with dates and dollar amounts where they matter."
    )


@dataclass
class _Question:
    desk: Desk
    deadline: float
    tools: dict[str, BaseTool]
    made: list[dict] = field(default_factory=list)
    requested: int = 0


def run(model: BaseChatModel, question: str, desk: Desk) -> dict:
    q = _Question(desk, monotonic() + QUESTION_DEADLINE_SECONDS, {t.name: t for t in TOOLS})
    messages: list[BaseMessage] = [SystemMessage(system_prompt(desk)), HumanMessage(question)]
    with_tools = model.bind_tools(TOOLS)
    for _ in range(MAX_MODEL_CALLS - 1):
        reply = _invoke(with_tools, messages, q)
        if not reply.tool_calls and not reply.invalid_tool_calls:
            return _answer(reply, q)
        messages.append(reply)
        messages.extend(_run_tool_call(call, q) for call in reply.tool_calls)
        messages.extend(
            _error_result(q, bad.get("id") or "", str(bad.get("name")),
                    f"The arguments for {bad.get('name')} could not be read: {bad.get('error')}")
            for bad in reply.invalid_tool_calls
        )
    final = model.bind_tools(TOOLS, tool_choice="none")
    return _answer(_invoke(final, messages, q), q)


def _invoke(model: Runnable, messages: list[BaseMessage], q: _Question) -> AIMessage:
    failure = None
    for _ in range(MODEL_ATTEMPTS):
        remaining = q.deadline - monotonic()
        if remaining <= 0:
            break
        try:
            return model.invoke(messages, timeout=min(MODEL_CALL_SECONDS, remaining))
        except Exception as exc:
            failure = exc
    if failure is None:
        raise Problem(502, "model_call_failed",
                      f"The question ran past its {QUESTION_DEADLINE_SECONDS}-second deadline.")
    raise Problem(502, "model_call_failed", f"The model call failed ({type(failure).__name__}).") from failure


def _answer(reply: AIMessage, q: _Question) -> dict:
    if not reply.text.strip():
        raise Problem(502, "model_call_failed", "The model returned an empty answer.")
    return {"answer": reply.text, "tool_calls": q.made}


def _submission_id(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        return int(value.strip())
    return None


def _error_result(q: _Question, call_id: str, name: str, reason: str, action: str = "tool_refused") -> ToolMessage:
    """Answers a tool call that was refused or failed with an error result, and records it in activity."""
    with q.desk.conn:
        record_activity(q.desk, action, f"{name}: {reason}", q.desk.clock())
    return ToolMessage(reason, tool_call_id=call_id, status="error")


def _run_tool_call(call: dict, q: _Question) -> ToolMessage:
    desk = q.desk
    name, args = call["name"], call.get("args") or {}
    q.requested += 1
    if q.requested > MAX_TOOL_CALLS:
        return _error_result(q, call["id"], name, f"This question has used its {MAX_TOOL_CALLS} tool calls.")
    tool = q.tools.get(name)
    if tool is None:
        return _error_result(q, call["id"], name, f"There is no tool named {name}.")
    tool_input = args
    if name in SCOPED_TO_SUBMISSION:
        asked = args.get("submission_id", desk.submission_id)
        if _submission_id(asked) != desk.submission_id:
            reason = f"Refused: this question is about submission {desk.submission_id}, not {asked!r}."
            return _error_result(q, call["id"], name, reason, action="scope_refused")
        if name == "save_note" and any(m["name"] == "save_note" for m in q.made):
            return _error_result(q, call["id"], name, "A note was already saved for this question.")
        tool_input = {**args, "submission_id": desk.submission_id, "desk": desk}
    try:
        result = tool.invoke(tool_input)
    except Exception as exc:
        reason = f"The tool failed: {type(exc).__name__}: {exc}"
        return _error_result(q, call["id"], name, reason, action="tool_failed")
    q.made.append({"name": name, "args": args})
    return ToolMessage(json.dumps(result, default=str), tool_call_id=call["id"])
