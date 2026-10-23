"""One Kora database, built once and shared by every test in here."""

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pytest

import kora
from kora import load


@dataclass
class BuiltDatabase:
    path: Path
    seconds: float
    con: duckdb.DuckDBPyConnection

    def one(self, sql, *params):
        return self.con.execute(sql, list(params)).fetchone()[0]

    def all(self, sql, *params):
        return self.con.execute(sql, list(params)).fetchall()


def checksums(db_path):
    """{table: (row count, order-independent hash)} for a database.

    Summing a hash of each row ignores row order, so two builds match
    only if they hold exactly the same rows.
    """
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return {
            name: con.execute(
                f"SELECT count(*), sum(hash(t))::VARCHAR FROM {name} t"
            ).fetchone()
            for name in load.TABLE_NAMES
        }
    finally:
        con.close()


@pytest.fixture(scope="session")
def kora_db(tmp_path_factory):
    # Building takes a while, so every test shares this one database.
    path = tmp_path_factory.mktemp("kora") / "kora.duckdb"
    result = kora.build(path)
    con = duckdb.connect(str(path), read_only=True)
    yield BuiltDatabase(path, result.seconds, con)
    con.close()
