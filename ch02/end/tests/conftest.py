"""Shared setup for chapter 2's tests: import paths and a tiny database."""

import sys
from pathlib import Path

import duckdb
import pytest

END = Path(__file__).resolve().parents[1]

# Chapter code imports its neighbours by plain name (from tools import
# run_sql), the same way ask.py does, so this chapter's folder must be
# on the path. Every chapter has its own agent.py, tools.py and so on,
# so forget any copies imported earlier and put this folder first.
# (The repo root, for kora, is added by pythonpath in pyproject.toml.)
for name in ("agent", "answer", "models", "questions", "tools"):
    sys.modules.pop(name, None)
sys.path.insert(0, str(END))


@pytest.fixture(scope="session")
def kora_db(tmp_path_factory):
    """The reader's Kora database, or a fresh build if there isn't one."""
    # Imported here so the path setup above has run first.
    import kora
    from kora.config import resolve_db_path

    path = resolve_db_path()
    if not path.exists():
        path = tmp_path_factory.mktemp("kora") / "kora.duckdb"
        kora.build(path)
    return path


@pytest.fixture
def tiny_db(tmp_path):
    """A small DuckDB file with two tables, so tests run in a blink."""
    path = tmp_path / "tiny.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE stores (store_id INTEGER, region VARCHAR);
        INSERT INTO stores VALUES (1, 'North'), (2, 'North'),
                                  (3, 'South');
        CREATE TABLE orders (order_id INTEGER, order_date DATE,
                             store_id INTEGER, revenue DECIMAL(12,2));
        INSERT INTO orders
        SELECT i, DATE '2026-08-01' + (i % 7)::INTEGER, i % 3 + 1,
               i * 1.25
        FROM range(1, 501) t(i);
    """)
    con.close()
    return path
