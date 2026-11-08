"""The run_sql tool: the only way the agent can see Kora's data."""

import re
import threading
from decimal import Decimal

import duckdb

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

COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def is_read_only(sql):
    """True if the statement starts with SELECT or WITH."""
    # This is a seat belt, not a checker. It stops an obvious DROP or
    # INSERT before it reaches the database, and nothing more. Chapter
    # 4 checks queries properly.
    text = COMMENTS.sub(" ", sql).strip().lower()
    return text.startswith(("select", "with"))


def execute(sql, db_path, limit, timeout_s):
    """Run sql on a read-only connection and fetch up to limit rows."""
    # read_only=True is the real safety net. DuckDB itself refuses any
    # write on this connection, whatever the SQL says.
    con = duckdb.connect(str(db_path), read_only=True)
    # DuckDB has no per-query timeout. So a timer thread waits, then
    # calls interrupt(), which cancels the running query with an error.
    timer = threading.Timer(timeout_s, con.interrupt)
    timer.start()
    try:
        cursor = con.execute(sql)
        columns = [column[0] for column in cursor.description]
        return columns, cursor.fetchmany(limit)
    finally:
        timer.cancel()
        con.close()


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


def run_sql(sql, db_path, max_rows=200, timeout_s=10):
    """Run one query read-only and return a JSON-safe result dict.

    Never raises on a bad query. The error goes back to the model as
    data, so it can read it and try again.
    """
    result = {"columns": [], "rows": [], "row_count": 0,
              "truncated": False, "error": None}
    if not is_read_only(sql):
        result["error"] = "Only SELECT or WITH queries are allowed."
        return result
    try:
        # Ask for one extra row. If it arrives, the answer was cut off.
        columns, rows = execute(sql, db_path, max_rows + 1, timeout_s)
    except duckdb.InterruptException:
        result["error"] = f"Query stopped after {timeout_s} seconds."
        return result
    except duckdb.Error as error:
        result["error"] = str(error)
        return result
    result["columns"] = columns
    result["rows"] = [[to_json(v) for v in row] for row in rows[:max_rows]]
    result["row_count"] = len(result["rows"])
    result["truncated"] = len(rows) > max_rows
    return result


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
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(SCHEMA_SQL).fetchall()
    finally:
        con.close()
    tables = {}
    for table, column, data_type in rows:
        tables.setdefault(table, []).append(f"{column} {data_type}")
    return "\n".join(f"{table}({', '.join(columns)})"
                     for table, columns in tables.items())
