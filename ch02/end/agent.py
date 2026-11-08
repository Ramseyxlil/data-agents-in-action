"""The agent loop, written by hand.

Ask the model. If it asks for a tool, run the tool and send back the
result. Repeat until it calls final_answer or runs out of turns.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import date

from answer import ANSWER_TOOL, Answer
from pydantic import ValidationError
from tools import RUN_SQL_TOOL, describe_schema, run_sql

try:
    # Kora's "today" lives in the repo's config. If the kora package
    # isn't on the path, fall back to the same date.
    from kora.config import AS_OF
except ImportError:
    AS_OF = date(2026, 8, 10)

# Deliberately naive: the schema and the date, nothing else. No
# business definitions, no calendar rules. Chapters 4 and 5 add those.
SYSTEM_PROMPT_TEMPLATE = """\
You are a data assistant for Kora, a retailer. You answer questions
about Kora's business from its DuckDB database.

Today is {weekday} {today}.

The database has these tables:
{schema}

Rules:
- Use the run_sql tool to get every fact. Never guess a number.
- Write DuckDB SQL using only the tables and columns listed above.
- If a query fails, read the error, fix the query and try again.
- When you have the answer, call final_answer. Put the headline
  number in "number" and list anything you assumed in "assumptions".
"""

NUDGE = "Please call final_answer with your answer."

# How many result rows the trace keeps, and how many --trace prints.
TRACE_ROWS = 20
PRINT_ROWS = 10


@dataclass
class AgentResult:
    answer: Answer | None = None
    trace: list = field(default_factory=list)
    turns: int = 0
    stopped_reason: str = "error"
    usage: dict = field(default_factory=dict)
    error: str | None = None


def build_system_prompt(db_path, as_of=None):
    """Fill the template with today's date and the database schema."""
    today = as_of or AS_OF
    return SYSTEM_PROMPT_TEMPLATE.format(
        weekday=today.strftime("%A"), today=today.isoformat(),
        schema=describe_schema(db_path))


def run_agent(question, model, db_path, max_turns=6, as_of=None):
    """Answer one question: ask the model, run its tools, repeat."""
    system = build_system_prompt(db_path, as_of)
    tools = [RUN_SQL_TOOL, ANSWER_TOOL]
    messages = [{"role": "user", "content": question}]
    result = AgentResult()
    nudged = False

    for turn in range(1, max_turns + 1):
        result.turns = turn
        reply = call_model(model, system, messages, tools, result)
        if reply is None:
            return result                    # the model call failed
        messages.append(assistant_message(reply))

        if not reply.tool_calls:             # plain text, no tool
            if nudged:
                result.error = "The model never called final_answer."
                return result
            nudged = True
            messages.append({"role": "user", "content": NUDGE})
            result.trace.append({"step": "nudge"})
            continue

        for call in reply.tool_calls:
            answer, output = handle_tool_call(call, db_path, result)
            if answer is not None:
                result.answer = answer
                result.stopped_reason = "answered"
                return result
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": output})

    result.stopped_reason = "max_turns"
    return result


def call_model(model, system, messages, tools, result):
    """Call the model once, recording time, tokens and any failure."""
    started = time.perf_counter()
    try:
        reply = model.complete(system, messages, tools)
    except Exception as error:
        # A network or API failure ends this question, not the program.
        result.error = f"{type(error).__name__}: {error}"
        result.trace.append({"step": "model_error",
                             "error": result.error})
        return None
    for key, count in reply.usage.items():
        result.usage[key] = result.usage.get(key, 0) + count
    result.trace.append({
        "step": "model", "text": reply.text,
        "tools": [call.name for call in reply.tool_calls],
        "seconds": round(time.perf_counter() - started, 2)})
    return reply


def assistant_message(reply):
    """The model's reply in our neutral message format."""
    calls = [{"id": c.id, "name": c.name, "arguments": c.arguments}
             for c in reply.tool_calls]
    return {"role": "assistant", "content": reply.text,
            "tool_calls": calls}


def handle_tool_call(call, db_path, result):
    """Run one tool call. Returns (answer, None) or (None, output)."""
    if call.name == "run_sql":
        return None, use_run_sql(call.arguments, db_path, result.trace)
    if call.name == "final_answer":
        try:
            return Answer.model_validate(call.arguments), None
        except ValidationError as error:
            # Send the problem back so the model can fix its answer.
            result.trace.append({"step": "answer_rejected",
                                 "error": str(error)})
            return None, f"final_answer was not valid: {error}"
    result.trace.append({"step": "unknown_tool", "tool": call.name})
    return None, f"There is no tool called {call.name}."


def use_run_sql(arguments, db_path, trace):
    """Run the model's SQL, record it in the trace, return JSON text."""
    sql = arguments.get("sql")
    trace.append({"step": "run_sql", "sql": sql})
    started = time.perf_counter()
    if isinstance(sql, str):
        output = run_sql(sql, db_path)
    else:
        output = {"error": "run_sql needs a string argument sql.",
                  "columns": [], "rows": [], "row_count": 0,
                  "truncated": False}
    # Keep what the model actually saw, so a reader can check its
    # answer against it later. 20 rows is enough to judge, and keeps
    # saved results small.
    trace.append({"step": "sql_result",
                  "row_count": output["row_count"],
                  "truncated": output["truncated"],
                  "error": output["error"],
                  "columns": output["columns"],
                  "rows": output["rows"][:TRACE_ROWS],
                  "seconds": round(time.perf_counter() - started, 2)})
    return json.dumps(output)


def format_trace(trace):
    """Turn a trace into readable lines for the terminal."""
    lines = []
    for step in trace:
        kind = step["step"]
        if kind == "model":
            asked = ", ".join(step["tools"]) or "no tool"
            lines.append(f"[model {step['seconds']}s] asks for {asked}")
            if step["text"]:
                lines.append(f"    says: {step['text'].strip()}")
        elif kind == "run_sql":
            lines.append("  run_sql:")
            sql = step["sql"] or "(no sql given)"
            lines += [f"      {line}" for line in sql.splitlines()]
        elif kind == "sql_result":
            if step["error"]:
                lines.append(f"  -> error: {step['error']}")
            else:
                cut = " (truncated)" if step["truncated"] else ""
                lines.append(f"  -> {step['row_count']} rows{cut} "
                             f"in {step['seconds']}s")
                lines += format_rows(step)
        else:
            detail = step.get("error") or step.get("tool") or ""
            lines.append(f"[{kind}] {detail}".rstrip())
    return "\n".join(lines)


def format_rows(step, limit=PRINT_ROWS):
    """The column names and first rows of a SQL result, as lines."""
    if not step.get("columns"):
        return []
    rows = step.get("rows") or []
    lines = ["       " + " | ".join(step["columns"])]
    lines += ["       " + " | ".join(str(value) for value in row)
              for row in rows[:limit]]
    hidden = step["row_count"] - min(len(rows), limit)
    if hidden > 0:
        lines.append(f"       ... {hidden} more rows not shown")
    return lines


def result_to_dict(result):
    """An AgentResult as plain data, ready for json.dumps."""
    answer = result.answer.model_dump() if result.answer else None
    return {"answer": answer, "stopped_reason": result.stopped_reason,
            "turns": result.turns, "usage": result.usage,
            "error": result.error, "trace": result.trace}
