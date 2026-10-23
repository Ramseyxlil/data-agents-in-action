"""Work out the numbers chapter 1 quotes, from the built database.

Run it with:  python -m kora.numbers

It writes ch01/numbers.json. The chapter text is checked against that
file, and the tests check the file against a fresh build, so the book
and the data can't drift apart without someone noticing.
"""

import argparse
import json
import sys

import duckdb

from kora import story
from kora.config import AS_OF, REPO_ROOT, resolve_db_path

LISTING_1_1 = REPO_ROOT / "ch01" / "listing_1_1.sql"
NUMBERS_JSON = REPO_ROOT / "ch01" / "numbers.json"

NORTH_WEEK_SQL = """
    SELECT COALESCE(SUM(o.revenue), 0)
    FROM orders o
    JOIN stores s ON o.store_id = s.store_id
    WHERE s.region = 'North'
      AND o.status = 'completed'
      AND o.order_date BETWEEN ? AND ?
"""

NET_SQL = """
    SELECT COALESCE(SUM(i.revenue), 0)
    FROM invoices i
    JOIN orders o ON i.order_id = o.order_id
    JOIN stores s ON o.store_id = s.store_id
    JOIN fiscal_calendar c ON i.invoice_date = c.calendar_date
    WHERE s.region = ? AND c.fiscal_year = ? AND c.fiscal_quarter = ?
"""

TARGET_SQL = """
    SELECT COALESCE(SUM(t.target_revenue), 0)
    FROM targets t
    JOIN stores s ON t.store_id = s.store_id
    WHERE s.region = ? AND t.fiscal_year = ? AND t.fiscal_quarter = ?
"""

FINANCE_SQL = """
    SELECT net_revenue
    FROM finance_closed_totals
    WHERE region = ? AND fiscal_year = ? AND fiscal_quarter = ?
"""

ORDERS_YEAR_SQL = """
    SELECT COALESCE(SUM(o.revenue), 0)
    FROM orders o
    JOIN stores s ON o.store_id = s.store_id
    JOIN fiscal_calendar c ON o.order_date = c.calendar_date
    WHERE s.region = ? AND c.fiscal_year = ?
"""

INVOICES_YEAR_SQL = """
    SELECT COALESCE(SUM(i.revenue), 0)
    FROM invoices i
    JOIN orders o ON i.order_id = o.order_id
    JOIN stores s ON o.store_id = s.store_id
    JOIN fiscal_calendar c ON i.invoice_date = c.calendar_date
    WHERE s.region = ? AND c.fiscal_year = ?
"""

PARTNER_YEAR_SQL = """
    SELECT COALESCE(SUM(p.revenue), 0)
    FROM partner_sales p
    JOIN stores s ON p.store_id = s.store_id
    JOIN fiscal_calendar c ON p.sale_month = c.calendar_date
    WHERE s.region = ? AND c.fiscal_year = ?
"""

LOADED_SQL = """
    SELECT loaded_through FROM data_loads WHERE table_name = 'invoices'
"""


def one(con, sql, *params):
    return con.execute(sql, list(params)).fetchone()[0]


def pct_change(new, old):
    return round(float((new - old) / old * 100), 1)


def cash(value):
    # DuckDB hands back exact decimals. JSON wants a plain number.
    return round(float(value), 2)


def compute(con):
    """Every number chapter 1 quotes, as a plain dict."""
    week_prev = one(con, NORTH_WEEK_SQL, *story.NORTH_WEEK_PREV)
    week_last = one(con, NORTH_WEEK_SQL, *story.NORTH_WEEK_LAST)

    year, quarter = story.NORTH_Q1
    q1_net = one(con, NET_SQL, "North", year, quarter)
    q1_target = one(con, TARGET_SQL, "North", year, quarter)
    finance = one(con, FINANCE_SQL, "North", year, quarter)

    listing_sql = LISTING_1_1.read_text(encoding="utf-8")
    listing = con.execute(listing_sql).fetchone()[0]

    fy2024 = 2024
    loaded = one(con, LOADED_SQL)

    return {
        "as_of": AS_OF.isoformat(),
        "finance_north_fy2027q1": cash(finance),
        "invoices_loaded_through": loaded.isoformat(),
        "listing_1_1_result": cash(listing),
        "listing_1_1_vs_finance_pct": pct_change(listing, finance),
        "north_fy2024_invoices_revenue": cash(
            one(con, INVOICES_YEAR_SQL, "North", fy2024)
        ),
        "north_fy2024_orders_revenue": cash(
            one(con, ORDERS_YEAR_SQL, "North", fy2024)
        ),
        "north_fy2024_partner_revenue": cash(
            one(con, PARTNER_YEAR_SQL, "North", fy2024)
        ),
        "north_fy2027q1_net": cash(q1_net),
        "north_fy2027q1_target": cash(q1_target),
        "north_fy2027q1_vs_target_pct": pct_change(q1_net, q1_target),
        "north_week_change_pct": pct_change(week_last, week_prev),
        "north_week_last": cash(week_last),
        "north_week_prev": cash(week_prev),
    }


def compute_for(db_path):
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return compute(con)
    finally:
        con.close()


def write_numbers(numbers, path=NUMBERS_JSON):
    text = json.dumps(numbers, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-path", help="database to read")
    args = parser.parse_args(argv)

    db_path = resolve_db_path(args.db_path)
    if not db_path.exists():
        print(f"No database at {db_path}.")
        print("Build it first: python scripts/setup_kora.py")
        return 1

    numbers = compute_for(db_path)
    write_numbers(numbers)
    print(f"Wrote {NUMBERS_JSON.relative_to(REPO_ROOT).as_posix()}")
    for key, value in numbers.items():
        print(f"    {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
