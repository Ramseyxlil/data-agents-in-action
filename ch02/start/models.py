"""One small interface to a chat model, with two providers and a fake.

The agent loop only ever calls complete(). It speaks our own neutral
message format, and each provider class converts it to and from what
its SDK expects. Swap the provider and the loop doesn't change.

Our neutral messages look like this:
    {"role": "user", "content": "How many stores..."}
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_1", "name": "run_sql", "arguments": {...}}]}
    {"role": "tool", "tool_call_id": "call_1", "content": "{...}"}
"""

# The imports below are the ones the finished file uses. Some are
# unused until you fill in the TODOs.
# ruff: noqa: F401

import copy
import json
import os
from dataclasses import dataclass, field
from typing import Protocol

import anthropic
import openai


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ModelReply:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)


class ChatModel(Protocol):
    def complete(self, system: str, messages: list[dict],
                 tools: list[dict]) -> ModelReply:
        """Send the conversation and tools, get the next reply."""


class MissingSetting(Exception):
    """A required setting is not in .env."""


def require(name):
    """Read a setting from the environment, or explain how to set it."""
    value = os.getenv(name)
    if not value:
        raise MissingSetting(
            f"{name} is not set. Add it to your .env file "
            f"(see .env.example).")
    return value


def parse_arguments(raw):
    """Turn a JSON string of tool arguments into a dict."""
    # Models sometimes send broken JSON. Keep the raw text so the tool
    # can report the problem back instead of crashing the loop.
    try:
        arguments = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"_unparsed": raw}
    return arguments if isinstance(arguments, dict) else {"_value": raw}


# ------------------------------------------------------------------
# OpenAI (Chat Completions)
# ------------------------------------------------------------------


def to_openai_tools(tools):
    """Neutral tool schemas to OpenAI's function tool format."""
    # TODO: wrap each tool as {'type': 'function', 'function': tool}.
    raise NotImplementedError


def to_openai_messages(system, messages):
    """Neutral messages to OpenAI chat messages, system first."""
    # OpenAI wants the arguments back as a JSON string.
    # TODO: put the system message first, turn tool calls and tool results
    #   into OpenAI's shapes.
    raise NotImplementedError


def from_openai_response(response):
    """An OpenAI chat completion to our ModelReply."""
    # TODO: read text, tool calls and token counts from
    #   choices[0].message.
    raise NotImplementedError


class OpenAIModel:
    """A chat model behind OpenAI's Chat Completions API."""

    def __init__(self, model, api_key):
        self.model = model
        self.client = openai.OpenAI(api_key=api_key)

    def complete(self, system, messages, tools):
        """Send the conversation and tools, get the next reply."""
        # Some reasoning models only accept their default
        # temperature. Try once more without it.
        # TODO: call client.chat.completions.create with temperature 0.
        raise NotImplementedError


# ------------------------------------------------------------------
# Anthropic (Messages API)
# ------------------------------------------------------------------


def to_anthropic_tools(tools):
    """Neutral tool schemas to Anthropic's input_schema format."""
    # TODO: rename parameters to input_schema.
    raise NotImplementedError


def to_anthropic_messages(messages):
    """Neutral messages to Anthropic messages (system goes apart)."""
    # Anthropic rejects an empty assistant turn.
    # Tool results go back inside a user turn, and results for
    # the same turn must share one user message.
    # TODO: turn tool calls into tool_use blocks and results into
    #   tool_result blocks in a user turn.
    raise NotImplementedError


def from_anthropic_response(response):
    """An Anthropic message to our ModelReply."""
    # TODO: collect text blocks, tool_use blocks and usage.
    raise NotImplementedError


class AnthropicModel:
    """A chat model behind Anthropic's Messages API."""

    def __init__(self, model, api_key, max_tokens=4096):
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=api_key)

    def complete(self, system, messages, tools):
        """Send the conversation and tools, get the next reply."""
        # The current Messages API has no temperature setting, so
        # there is nothing to pin to 0 here.
        # TODO: call client.messages.create with system, messages and
        #   tools.
        raise NotImplementedError


# ------------------------------------------------------------------
# A fake model for tests: no key, no network, no cost
# ------------------------------------------------------------------


class FakeModel:
    """Replays scripted replies in order and records every call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, messages, tools):
        """Record what the agent sent, return the next scripted reply."""
        # Deep copy, because the agent keeps adding to the same list.
        self.calls.append({"system": system,
                           "messages": copy.deepcopy(messages),
                           "tools": tools})
        if not self.replies:
            raise RuntimeError("FakeModel has no scripted replies left.")
        return self.replies.pop(0)


def make_model(provider=None):
    """Build the model named by provider, or by MODEL_PROVIDER in .env."""
    # TODO: pick OpenAIModel or AnthropicModel from MODEL_PROVIDER, using
    #   require() for settings.
    raise NotImplementedError
