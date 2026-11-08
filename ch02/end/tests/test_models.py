"""Format conversion for both providers. No network, no SDK calls."""

from types import SimpleNamespace

import pytest
from models import (
    FakeModel,
    MissingSetting,
    ModelReply,
    from_anthropic_response,
    from_openai_response,
    make_model,
    to_anthropic_messages,
    to_anthropic_tools,
    to_openai_messages,
    to_openai_tools,
)

TOOL = {"name": "run_sql", "description": "Run SQL.",
        "parameters": {"type": "object",
                       "properties": {"sql": {"type": "string"}},
                       "required": ["sql"]}}

CONVERSATION = [
    {"role": "user", "content": "How many stores?"},
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "a", "name": "run_sql", "arguments": {"sql": "SELECT 1"}},
        {"id": "b", "name": "run_sql", "arguments": {"sql": "SELECT 2"}},
    ]},
    {"role": "tool", "tool_call_id": "a", "content": '{"rows": [[1]]}'},
    {"role": "tool", "tool_call_id": "b", "content": '{"rows": [[2]]}'},
]


def test_openai_tools_wrap_the_schema_as_a_function():
    """OpenAI wants each tool inside a function object."""
    assert to_openai_tools([TOOL]) == [{"type": "function",
                                        "function": TOOL}]


def test_openai_messages():
    """System goes first, arguments become JSON strings."""
    out = to_openai_messages("Be useful.", CONVERSATION)
    assert out[0] == {"role": "system", "content": "Be useful."}
    call = out[2]["tool_calls"][0]
    assert call["type"] == "function"
    assert call["function"] == {"name": "run_sql",
                                "arguments": '{"sql": "SELECT 1"}'}
    assert out[3] == {"role": "tool", "tool_call_id": "a",
                      "content": '{"rows": [[1]]}'}


def test_openai_response_to_reply():
    """Tool calls, text and token counts come back in our format."""
    call = SimpleNamespace(id="x", function=SimpleNamespace(
        name="run_sql", arguments='{"sql": "SELECT 1"}'))
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content="Checking.", tool_calls=[call]))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=3))
    reply = from_openai_response(response)
    assert reply.text == "Checking."
    assert reply.tool_calls[0].arguments == {"sql": "SELECT 1"}
    assert reply.usage == {"input_tokens": 10, "output_tokens": 3}


def test_openai_broken_json_arguments_do_not_crash():
    """Bad JSON from the model becomes data the tool can report."""
    call = SimpleNamespace(id="x", function=SimpleNamespace(
        name="run_sql", arguments="{not json"))
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=None, tool_calls=[call]))], usage=None)
    reply = from_openai_response(response)
    assert reply.tool_calls[0].arguments == {"_unparsed": "{not json"}


def test_anthropic_tools_use_input_schema():
    """Anthropic calls the JSON schema input_schema."""
    assert to_anthropic_tools([TOOL]) == [{
        "name": "run_sql", "description": "Run SQL.",
        "input_schema": TOOL["parameters"]}]


def test_anthropic_messages():
    """Tool calls become tool_use blocks, results share one user turn."""
    out = to_anthropic_messages(CONVERSATION)
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert out[1]["content"][0] == {
        "type": "tool_use", "id": "a", "name": "run_sql",
        "input": {"sql": "SELECT 1"}}
    results = out[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]
    assert results[0]["type"] == "tool_result"


def test_anthropic_empty_assistant_turn_gets_placeholder():
    """Anthropic rejects an assistant turn with no content."""
    out = to_anthropic_messages([{"role": "assistant", "content": None,
                                  "tool_calls": []}])
    assert out[0]["content"] == [{"type": "text", "text": "(no reply)"}]


def test_anthropic_response_to_reply():
    """Text and tool_use blocks come back in our format."""
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Checking."),
                 SimpleNamespace(type="tool_use", id="t1",
                                 name="run_sql",
                                 input={"sql": "SELECT 1"})],
        usage=SimpleNamespace(input_tokens=12, output_tokens=4))
    reply = from_anthropic_response(response)
    assert reply.text == "Checking."
    assert reply.tool_calls[0].id == "t1"
    assert reply.usage == {"input_tokens": 12, "output_tokens": 4}


def test_fake_model_replays_and_records():
    """The fake returns scripted replies and keeps copies of calls."""
    fake = FakeModel([ModelReply("one"), ModelReply("two")])
    messages = [{"role": "user", "content": "hi"}]
    assert fake.complete("sys", messages, []).text == "one"
    messages.append({"role": "user", "content": "again"})
    assert fake.complete("sys", messages, []).text == "two"
    assert len(fake.calls[0]["messages"]) == 1


@pytest.mark.parametrize("provider, missing", [
    ("openai", "OPENAI_MODEL"),
    ("anthropic", "ANTHROPIC_MODEL"),
])
def test_make_model_names_the_missing_setting(monkeypatch, provider,
                                              missing):
    """A missing setting says exactly what to put in .env."""
    for name in ("OPENAI_MODEL", "OPENAI_API_KEY", "ANTHROPIC_MODEL",
                 "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(MissingSetting, match=missing):
        make_model(provider)


def test_make_model_rejects_unknown_provider():
    """A typo in MODEL_PROVIDER gets a clear message."""
    with pytest.raises(MissingSetting, match="openai or anthropic"):
        make_model("azure")
