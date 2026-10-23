"""Run listing 1.1 against Kora's database and print the result.

This is the wrong query from section 1.2. It runs fine and returns a
confident number. The number is just not the one finance reports.
"""

import sys
from pathlib import Path

import duckdb

# Let Python find the kora package in the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from kora.config import resolve_db_path  # noqa: E402

LISTING = Path(__file__).resolve().parent / "listing_1_1.sql"


def main():
    db_path = resolve_db_path()
    if not db_path.exists():
        print(f"No database at {db_path}.")
        print("Build it first: python scripts/setup_kora.py")
        return 1

    sql = LISTING.read_text(encoding="utf-8")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        (revenue,) = con.execute(sql).fetchone()
    finally:
        con.close()

    print("Listing 1.1: North revenue, April to June 2026")
    print(f"    {revenue:,.2f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
