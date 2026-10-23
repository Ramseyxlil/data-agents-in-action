"""Kora's dataset lives here. The generator is built in chapter 1.

Call build() to make the database, or run scripts/setup_kora.py.
"""

import time
from dataclasses import dataclass

from kora import config, generate, load


@dataclass
class BuildResult:
    row_counts: dict
    seconds: float


def build(db_path, seed=config.SEED, noise_tables=0, parquet_dir=None):
    """Build Kora's database at db_path and return row counts and time.

    The same seed always gives the same data.
    """
    started = time.perf_counter()
    tables = generate.generate_tables(seed)
    noise = generate.noise_tables(seed, noise_tables)
    load.load_database(db_path, tables, noise)
    if parquet_dir is not None:
        load.export_parquet(db_path, parquet_dir)
    counts = load.row_counts(db_path)
    return BuildResult(counts, time.perf_counter() - started)


__all__ = ["BuildResult", "build"]
