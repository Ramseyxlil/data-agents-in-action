"""The agent loop, driven by a scripted FakeModel. No key needed."""

import json
from datetime import date

from agent import (
    SYSTEM_PROMPT_TEMPLATE,
    build_system_prompt,
    format_trace,
    run_agent,
)
from models import FakeModel, ModelReply, ToolCall

COUNT_SQL = "SELECT COUNT(*) FROM stores WHERE region = 'North'"
ANSWER = {
    "value": "North has 2 stores.", "number": 2, "unit": "stores",
    "sql": COUNT_SQL, "rows_used": 1,
    "explanation": "Counted North rows in stores.",
}


def sql_call(sql, call_id="c1"):
    return ModelReply(None, [ToolCall(call_id, "run_sql", {"sql": sql})])


def answer_call(arguments, call_id="c9"):
    return ModelReply(None, [ToolCall(call_id, "final_answer",
                                      arguments)])


def last_tool_output(model):
    """The content of the last tool message the agent sent."""
    message = model.calls[-1]["messages"][-1]
    assert message["role"] == "tool"
    return message["content"]


def test_question_sql_answer(tiny_db):
    """The happy path: one query, then a structured answer."""
    model = FakeModel([sql_call(COUNT_SQL), answer_call(ANSWER)])
    result = run_agent("How many North stores?", model, tiny_db)
    assert result.stopped_reason == "answered"
    assert result.answer.number == 2
    assert result.turns == 2
    assert json.loads(last_tool_output(model))["rows"] == [[2]]
    steps = [step["step"] for step in result.trace]
    assert steps == ["model", "run_sql", "sql_result", "model"]
    sql_result = result.trace[2]
    assert sql_result["columns"] == ["count_star()"]
    assert sql_result["rows"] == [[2]]


def test_trace_keeps_the_first_20_rows_the_model_saw(tiny_db):
    """The trace shows what came back, capped so results stay small."""
    sql = "SELECT order_id, revenue FROM orders ORDER BY order_id"
    model = FakeModel([sql_call(sql), answer_call(ANSWER)])
    result = run_agent("List orders", model, tiny_db)
    step = next(s for s in result.trace if s["step"] == "sql_result")
    assert step["row_count"] == 200
    assert step["columns"] == ["order_id", "revenue"]
    assert step["rows"] == [[n, n * 1.25] for n in range(1, 21)]


def test_format_trace_prints_at_most_10_rows(tiny_db):
    """--trace shows the columns and 10 rows, then says what's hidden."""
    sql = "SELECT order_id FROM orders ORDER BY order_id LIMIT 15"
    model = FakeModel([sql_call(sql), answer_call(ANSWER)])
    text = format_trace(run_agent("List orders", model, tiny_db).trace)
    lines = [line.strip() for line in text.splitlines()]
    assert "order_id" in lines
    assert "10" in lines and "11" not in lines
    assert "... 5 more rows not shown" in lines


def test_format_trace_with_an_error_prints_no_rows(tiny_db):
    """A failed query shows its error, not an empty table."""
    model = FakeModel([sql_call("SELECT nope FROM stores"),
                       answer_call(ANSWER)])
    text = format_trace(run_agent("How many?", model, tiny_db).trace)
    assert "-> error:" in text
    assert "rows not shown" not in text


def test_sql_error_is_fed_back_and_agent_recovers(tiny_db):
    """A bad query's error reaches the model, which fixes it."""
    model = FakeModel([sql_call("SELECT nope FROM stores", "c1"),
                       sql_call(COUNT_SQL, "c2"), answer_call(ANSWER)])
    result = run_agent("How many North stores?", model, tiny_db)
    assert result.stopped_reason == "answered"
    sent_back = model.calls[1]["messages"][-1]
    assert sent_back["tool_call_id"] == "c1"
    assert "nope" in json.loads(sent_back["content"])["error"]


def test_invalid_final_answer_gets_the_error_back(tiny_db):
    """A malformed answer is rejected and the model may try again."""
    broken = {k: v for k, v in ANSWER.items() if k != "sql"}
    model = FakeModel([answer_call(broken), answer_call(ANSWER)])
    result = run_agent("How many North stores?", model, tiny_db)
    assert result.stopped_reason == "answered"
    assert "final_answer was not valid" in last_tool_output(model)
    assert "sql" in last_tool_output(model)


def test_max_turns_stops_the_loop(tiny_db):
    """An agent that never answers must still stop."""
    model = FakeModel([sql_call(COUNT_SQL, f"c{n}") for n in range(3)])
    result = run_agent("How many?", model, tiny_db, max_turns=3)
    assert result.answer is None
    assert result.stopped_reason == "max_turns"
    assert result.turns == 3


def test_plain_text_gets_one_nudge(tiny_db):
    """Plain text instead of a tool call earns exactly one reminder."""
    model = FakeModel([ModelReply("There are 2.", []),
                       answer_call(ANSWER)])
    result = run_agent("How many North stores?", model, tiny_db)
    assert result.stopped_reason == "answered"
    assert model.calls[1]["messages"][-1]["role"] == "user"
    assert "final_answer" in model.calls[1]["messages"][-1]["content"]


def test_second_plain_text_reply_stops(tiny_db):
    """After one nudge, more plain text ends the run without looping."""
    model = FakeModel([ModelReply("Two.", []), ModelReply("Two!", [])])
    result = run_agent("How many North stores?", model, tiny_db)
    assert result.answer is None
    assert result.stopped_reason == "error"
    assert result.turns == 2


def test_system_prompt_has_schema_and_date_but_no_business_rules(
        tiny_db):
    """Chapter 2's agent is naive on purpose: schema and date only."""
    prompt = build_system_prompt(tiny_db, as_of=date(2026, 8, 10))
    assert "stores(store_id INTEGER, region VARCHAR)" in prompt
    assert "Monday 2026-08-10" in prompt
    for word in ("fiscal", "net revenue", "invoice", "finance",
                 "quarter"):
        assert word not in SYSTEM_PROMPT_TEMPLATE.lower()
        assert word not in prompt.lower()
    assert len(SYSTEM_PROMPT_TEMPLATE.splitlines()) < 25


def test_agent_sends_the_system_prompt_and_both_tools(tiny_db):
    """The model gets the schema prompt and exactly two tools."""
    model = FakeModel([answer_call(ANSWER)])
    run_agent("How many North stores?", model, tiny_db)
    sent = model.calls[0]
    assert "stores(store_id INTEGER" in sent["system"]
    assert [t["name"] for t in sent["tools"]] == ["run_sql",
                                                  "final_answer"]
