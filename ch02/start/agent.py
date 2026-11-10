"""The agent loop, written by hand.

Ask the model. If it asks for a tool, run the tool and send back the
result. Repeat until it calls final_answer or runs out of turns.
"""

# The imports below are the ones the finished file uses. Some are
# unused until you fill in the TODOs.
# ruff: noqa: F401

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

# Listing 2.3: the naive system prompt
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
    # TODO: fill SYSTEM_PROMPT_TEMPLATE with the weekday, date and
    #   describe_schema().
    raise NotImplementedError


# Listing 2.4: the agent loop
def run_agent(question, model, db_path, max_turns=6, as_of=None):
    """Answer one question: ask the model, run its tools, repeat."""
    # TODO: loop up to max_turns: call the model, handle plain text with
    #   one nudge, run each tool call, return on a valid final_answer.
    raise NotImplementedError


def call_model(model, system, messages, tools, result):
    """Call the model once, recording time, tokens and any failure."""
    # A network or API failure ends this question, not the program.
    # TODO: call model.complete, add up usage, append a 'model' step to
    #   the trace, return None on failure.
    raise NotImplementedError


def assistant_message(reply):
    """The model's reply in our neutral message format."""
    calls = [{"id": c.id, "name": c.name, "arguments": c.arguments}
             for c in reply.tool_calls]
    return {"role": "assistant", "content": reply.text,
            "tool_calls": calls}


# Listing 2.9: running one tool call
def handle_tool_call(call, db_path, result):
    """Run one tool call. Returns (answer, None) or (None, output)."""
    # Send the problem back so the model can fix its answer.
    # TODO: run_sql goes to use_run_sql, final_answer is validated with
    #   pydantic.
    raise NotImplementedError


def use_run_sql(arguments, db_path, trace):
    """Run the model's SQL, record it in the trace, return JSON text."""
    # Keep what the model actually saw, so a reader can check its
    # answer against it later. 20 rows is enough to judge, and keeps
    # saved results small.
    # TODO: run the SQL, record a run_sql step and a sql_result step (with
    #   the columns and the first TRACE_ROWS rows), return the result as
    #   JSON text.
    raise NotImplementedError


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
