from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from pydantic import Field


def tool_call(name: str, call_id: str = "call_1", **args) -> dict:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def tool_name(tool) -> str | None:
    if isinstance(tool, dict):
        return tool.get("name") or (tool.get("function") or {}).get("name")
    return getattr(tool, "name", None) or getattr(tool, "__name__", None)


class FakeChatModel(BaseChatModel):
    """Replays scripted replies in order; the last reply repeats once the script runs out. A call whose reply is an
    exception raises it, and one whose reply is a function returns or raises what the function does.

    `bind_tools` returns the model itself and records its arguments; each call records the bind in force and the
    timeout it was given."""

    replies: list = Field(default_factory=list)
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    binds: list[dict] = Field(default_factory=list)
    call_binds: list[dict] = Field(default_factory=list)
    timeouts: list[float | None] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake-desk-model"

    def bind_tools(self, tools, **kwargs):
        self.binds.append({"tools": [tool_name(t) for t in tools], "given": list(tools), **kwargs})
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(list(messages))
        self.call_binds.append(self.binds[-1] if self.binds else {})
        self.timeouts.append(kwargs.get("timeout"))
        reply = self.replies[min(len(self.calls), len(self.replies)) - 1]
        if callable(reply):
            reply = reply()
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(generations=[ChatGeneration(message=reply)])


class PayloadRecordingOpenAI(ChatOpenAI):
    """The real OpenAI chat model with its own bind_tools; each call builds the request payload it would send,
    records it, and replays a scripted reply instead of sending it."""

    replies: list[AIMessage] = Field(default_factory=list)
    payloads: list[dict] = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.payloads.append(self._get_request_payload(messages, stop=stop, **kwargs))
        reply = self.replies[min(len(self.payloads), len(self.replies)) - 1]
        return ChatResult(generations=[ChatGeneration(message=reply)])
