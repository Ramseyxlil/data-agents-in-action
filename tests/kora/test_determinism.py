"""The same seed must give the same data, or the book's numbers drift."""

import kora
from kora.config import SEED

from .conftest import checksums


def test_same_seed_gives_identical_tables(kora_db, tmp_path):
    """Every reader must get exactly the numbers printed in the book."""
    again = tmp_path / "again.duckdb"
    kora.build(again, seed=SEED)
    assert checksums(again) == checksums(kora_db.path)


def test_different_seed_gives_different_data(kora_db, tmp_path):
    """The seed must really drive the data, not just sit in config."""
    other = tmp_path / "other.duckdb"
    kora.build(other, seed=SEED + 1)
    ours, theirs = checksums(kora_db.path), checksums(other)
    assert ours["orders"] != theirs["orders"]
    assert ours["order_lines"] != theirs["order_lines"]
