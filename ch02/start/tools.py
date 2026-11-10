"""The run_sql tool: the only way the agent can see Kora's data."""

# The imports below are the ones the finished file uses. Some are
# unused until you fill in the TODOs.
# ruff: noqa: F401

import re
import threading
from decimal import Decimal

import duckdb

# Listing 2.5: the run_sql tool as a JSON schema
# The tool as the model sees it. The model never runs anything itself.
# It asks for run_sql with an sql argument, and our code runs it.
RUN_SQL_TOOL = {
    "name": "run_sql",
    "description": (
        "Run one read-only DuckDB SQL query against Kora's database "
        "and get the rows back. Use only the tables and columns in "
        "the schema you were given. Only SELECT or WITH queries work."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "The DuckDB SQL query to run.",
            },
        },
        "required": ["sql"],
    },
}

# Listing 2.7: the read-only guard and the timed query
COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def is_read_only(sql):
    """True if the statement starts with SELECT or WITH."""
    # This is a seat belt, not a checker. It stops an obvious DROP or
    # INSERT before it reaches the database, and nothing more. Chapter
    # 4 checks queries properly.
    # TODO: strip comments, then check the statement starts with select or
    #   with.
    raise NotImplementedError


def execute(sql, db_path, limit, timeout_s):
    """Run sql on a read-only connection and fetch up to limit rows."""
    # read_only=True is the real safety net. DuckDB itself refuses any
    # write on this connection, whatever the SQL says.
    # DuckDB has no per-query timeout. So a timer thread waits, then
    # calls interrupt(), which cancels the running query with an error.
    # TODO: open DuckDB read-only, start a Timer that calls
    #   con.interrupt(), run the query, fetch up to limit rows.
    raise NotImplementedError


def to_json(value):
    """Turn one database value into something json.dumps accepts."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    # Money comes back as an exact Decimal. A float is plenty for an
    # answer, and JSON has no decimal type.
    if isinstance(value, Decimal):
        return float(value)
    # Dates and anything unusual become text, like 2026-08-10.
    return str(value)


# Listing 2.8: run_sql, with errors returned as data
def run_sql(sql, db_path, max_rows=200, timeout_s=10):
    """Run one query read-only and return a JSON-safe result dict.

    Never raises on a bad query. The error goes back to the model as
    data, so it can read it and try again.
    """
    # Ask for one extra row. If it arrives, the answer was cut off.
    # TODO: guard, execute, catch errors into result['error'], cap rows
    #   and set truncated.
    raise NotImplementedError


# Listing 2.6: the schema text the model gets
SCHEMA_SQL = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'main'
    ORDER BY table_name, ordinal_position
"""


def describe_schema(db_path):
    """List every table with its columns and types, one per line."""
    # Names and types only. No meanings, no comments, no sample rows.
    # That is all a naive agent gets, and section 2.5 shows what that
    # costs.
    # TODO: query information_schema.columns and build one line per table.
    raise NotImplementedError
