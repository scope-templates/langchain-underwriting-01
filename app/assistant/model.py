import os
import re

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

MODEL_NAME = "gpt-4.1-mini"
PLACEHOLDER = re.compile(r"^(<.*>|\$\{.*\}|x+|\.+|\*+|sk-\.*|sk-x+|change-?me|replace-?me|your[-_ ].*|none|null)$",
                         re.IGNORECASE)


def api_key() -> str | None:
    """OPENAI_API_KEY from the process environment; blank or placeholder values count as unset."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or PLACEHOLDER.match(key):
        return None
    return key


def build_model() -> BaseChatModel | None:
    key = api_key()
    if key is None:
        return None
    return ChatOpenAI(model=MODEL_NAME, api_key=key, max_retries=0)
