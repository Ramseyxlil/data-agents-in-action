"""The run_sql tool: reads work, writes never do, and nothing hangs."""

import time

import duckdb
import pytest
from tools import describe_schema, execute, is_read_only, run_sql


def test_select_returns_rows(tiny_db):
    """A plain SELECT comes back as columns and JSON-safe rows."""
    result = run_sql(
        "SELECT store_id, region FROM stores ORDER BY store_id", tiny_db)
    assert result["error"] is None
    assert result["columns"] == ["store_id", "region"]
    assert result["rows"][0] == [1, "North"]
    assert result["row_count"] == 3
    assert result["truncated"] is False


def test_dates_and_decimals_become_json_safe(tiny_db):
    """Dates and Decimals must survive json.dumps for the model."""
    result = run_sql(
        "SELECT order_date, revenue FROM orders WHERE order_id = 4",
        tiny_db)
    assert result["rows"] == [["2026-08-05", 5.0]]


@pytest.mark.parametrize("sql", [
    "INSERT INTO stores VALUES (9, 'East')",
    "DROP TABLE stores",
    "UPDATE stores SET region = 'East'",
    "-- looks harmless\nDELETE FROM stores",
])
def test_guard_rejects_writes(tiny_db, sql):
    """The seat belt stops obvious writes before they run."""
    assert not is_read_only(sql)
    result = run_sql(sql, tiny_db)
    assert "Only SELECT or WITH" in result["error"]


def test_with_and_comments_are_allowed():
    """CTEs and leading comments are normal read queries."""
    assert is_read_only("/* total */ WITH x AS (SELECT 1) SELECT * FROM x")


def test_read_only_connection_blocks_writes(tiny_db):
    """Even past the guard, DuckDB itself refuses to write."""
    with pytest.raises(duckdb.Error):
        execute("INSERT INTO stores VALUES (9, 'East')", tiny_db, 10, 5)
    assert run_sql("SELECT COUNT(*) FROM stores", tiny_db)["rows"] == [[3]]


def test_row_cap_sets_truncated(tiny_db):
    """Large results are cut off, and the model is told so."""
    result = run_sql("SELECT * FROM orders", tiny_db, max_rows=50)
    assert result["row_count"] == 50
    assert result["truncated"] is True


def test_bad_column_returns_error_not_exception(tiny_db):
    """A broken query is data for the model, not a crash."""
    result = run_sql("SELECT no_such_column FROM stores", tiny_db)
    assert result["error"] and "no_such_column" in result["error"]
    assert result["rows"] == []


def test_timeout_interrupts_slow_query(tiny_db):
    """A runaway query must not hang the agent."""
    started = time.perf_counter()
    result = run_sql(
        "SELECT COUNT(*) FROM range(100000000) a, range(100000000) b",
        tiny_db, timeout_s=0.5)
    assert "stopped after" in result["error"]
    assert time.perf_counter() - started < 10


def test_describe_schema_lists_names_and_types_only(tiny_db):
    """The naive agent sees table and column names, nothing else."""
    schema = describe_schema(tiny_db)
    assert schema.splitlines() == [
        "orders(order_id INTEGER, order_date DATE, store_id INTEGER, "
        "revenue DECIMAL(12,2))",
        "stores(store_id INTEGER, region VARCHAR)",
    ]
