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
    return [{"type": "function", "function": tool} for tool in tools]


def to_openai_messages(system, messages):
    """Neutral messages to OpenAI chat messages, system first."""
    out = [{"role": "system", "content": system}]
    for message in messages:
        if message["role"] == "tool":
            out.append({"role": "tool",
                        "tool_call_id": message["tool_call_id"],
                        "content": message["content"]})
        elif message.get("tool_calls"):
            # OpenAI wants the arguments back as a JSON string.
            calls = [{"id": call["id"], "type": "function",
                      "function": {"name": call["name"],
                                   "arguments": json.dumps(
                                       call["arguments"])}}
                     for call in message["tool_calls"]]
            out.append({"role": "assistant",
                        "content": message.get("content"),
                        "tool_calls": calls})
        else:
            out.append({"role": message["role"],
                        "content": message["content"]})
    return out


def from_openai_response(response):
    """An OpenAI chat completion to our ModelReply."""
    message = response.choices[0].message
    calls = [ToolCall(call.id, call.function.name,
                      parse_arguments(call.function.arguments))
             for call in message.tool_calls or []
             if getattr(call, "function", None)]
    usage = {}
    if response.usage:
        usage = {"input_tokens": response.usage.prompt_tokens,
                 "output_tokens": response.usage.completion_tokens}
    return ModelReply(message.content, calls, usage)


class OpenAIModel:
    """A chat model behind OpenAI's Chat Completions API."""

    def __init__(self, model, api_key):
        self.model = model
        self.client = openai.OpenAI(api_key=api_key)

    def complete(self, system, messages, tools):
        """Send the conversation and tools, get the next reply."""
        request = {"model": self.model,
                   "messages": to_openai_messages(system, messages),
                   "tools": to_openai_tools(tools),
                   "temperature": 0}
        try:
            response = self.client.chat.completions.create(**request)
        except openai.BadRequestError as error:
            # Some reasoning models only accept their default
            # temperature. Try once more without it.
            if "temperature" not in str(error):
                raise
            del request["temperature"]
            response = self.client.chat.completions.create(**request)
        return from_openai_response(response)


# ------------------------------------------------------------------
# Anthropic (Messages API)
# ------------------------------------------------------------------


def to_anthropic_tools(tools):
    """Neutral tool schemas to Anthropic's input_schema format."""
    return [{"name": tool["name"],
             "description": tool["description"],
             "input_schema": tool["parameters"]} for tool in tools]


def to_anthropic_messages(messages):
    """Neutral messages to Anthropic messages (system goes apart)."""
    out = []
    for message in messages:
        if message["role"] == "assistant":
            blocks = []
            if message.get("content"):
                blocks.append({"type": "text",
                               "text": message["content"]})
            for call in message.get("tool_calls") or []:
                blocks.append({"type": "tool_use", "id": call["id"],
                               "name": call["name"],
                               "input": call["arguments"]})
            # Anthropic rejects an empty assistant turn.
            if not blocks:
                blocks.append({"type": "text", "text": "(no reply)"})
            out.append({"role": "assistant", "content": blocks})
        elif message["role"] == "tool":
            block = {"type": "tool_result",
                     "tool_use_id": message["tool_call_id"],
                     "content": message["content"]}
            # Tool results go back inside a user turn, and results for
            # the same turn must share one user message.
            last = out[-1] if out else None
            if (last and last["role"] == "user"
                    and isinstance(last["content"], list)):
                last["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            out.append({"role": "user", "content": message["content"]})
    return out


def from_anthropic_response(response):
    """An Anthropic message to our ModelReply."""
    texts = [block.text for block in response.content
             if block.type == "text"]
    calls = [ToolCall(block.id, block.name, dict(block.input))
             for block in response.content if block.type == "tool_use"]
    usage = {"input_tokens": response.usage.input_tokens,
             "output_tokens": response.usage.output_tokens}
    return ModelReply("\n".join(texts) or None, calls, usage)


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
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=to_anthropic_messages(messages),
            tools=to_anthropic_tools(tools),
        )
        return from_anthropic_response(response)


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
    provider = (provider or os.getenv("MODEL_PROVIDER") or "openai")
    provider = provider.strip().lower()
    if provider == "openai":
        return OpenAIModel(require("OPENAI_MODEL"),
                           require("OPENAI_API_KEY"))
    if provider == "anthropic":
        return AnthropicModel(require("ANTHROPIC_MODEL"),
                              require("ANTHROPIC_API_KEY"))
    raise MissingSetting(
        f"MODEL_PROVIDER={provider!r} is not supported in chapter 2. "
        f"Set it to openai or anthropic in your .env file.")
