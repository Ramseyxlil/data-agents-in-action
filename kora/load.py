"""Write Kora's tables to CSV files, then load them into DuckDB.

CSV is the simplest format DuckDB reads fast, and it needs no extra
packages. The CSV files live in a temporary folder and are gone once
the database is built.
"""

import csv
import os
import tempfile
from pathlib import Path

import duckdb

# Each table: (name, [(column, type)], [extra constraints]). The column
# order here is the order the book quotes and the generator writes.
TABLES = (
    ("regions", (
        ("region_id", "INTEGER PRIMARY KEY"),
        ("region_name", "VARCHAR"),
    ), ()),
    ("warehouses", (
        ("warehouse_id", "INTEGER PRIMARY KEY"),
        ("warehouse_name", "VARCHAR"),
        ("region", "VARCHAR"),
    ), ()),
    ("stores", (
        ("store_id", "INTEGER PRIMARY KEY"),
        ("store_name", "VARCHAR"),
        ("region", "VARCHAR"),
        ("warehouse_id", "INTEGER REFERENCES warehouses"),
        ("city", "VARCHAR"),
        ("opened_on", "DATE"),
        ("closed_on", "DATE"),
        ("is_active", "BOOLEAN"),
    ), ()),
    ("products", (
        ("product_id", "INTEGER PRIMARY KEY"),
        ("sku", "VARCHAR"),
        ("product_name", "VARCHAR"),
        ("category", "VARCHAR"),
        ("description", "VARCHAR"),
        ("unit_price", "DECIMAL(10,2)"),
        ("unit_cost", "DECIMAL(10,2)"),
    ), ()),
    ("customers", (
        ("customer_id", "INTEGER PRIMARY KEY"),
        ("customer_type", "VARCHAR"),
        ("home_store_id", "INTEGER REFERENCES stores"),
        ("created_on", "DATE"),
    ), ()),
    ("sales_reps", (
        ("rep_id", "INTEGER PRIMARY KEY"),
        ("rep_code", "VARCHAR"),
        ("store_id", "INTEGER REFERENCES stores"),
        ("region", "VARCHAR"),
        ("hired_on", "DATE"),
    ), ()),
    ("orders", (
        ("order_id", "INTEGER PRIMARY KEY"),
        ("order_date", "DATE"),
        ("store_id", "INTEGER REFERENCES stores"),
        ("customer_id", "INTEGER REFERENCES customers"),
        ("rep_id", "INTEGER REFERENCES sales_reps"),
        ("channel", "VARCHAR"),
        ("status", "VARCHAR"),
        ("revenue", "DECIMAL(12,2)"),
    ), ()),
    ("order_lines", (
        ("order_line_id", "INTEGER PRIMARY KEY"),
        ("order_id", "INTEGER REFERENCES orders"),
        ("product_id", "INTEGER REFERENCES products"),
        ("quantity", "INTEGER"),
        ("unit_price", "DECIMAL(10,2)"),
        ("discount_amount", "DECIMAL(10,2)"),
        ("line_amount", "DECIMAL(12,2)"),
    ), ()),
    ("returns", (
        ("return_id", "INTEGER PRIMARY KEY"),
        ("order_id", "INTEGER REFERENCES orders"),
        ("order_line_id", "INTEGER REFERENCES order_lines"),
        ("return_date", "DATE"),
        ("quantity", "INTEGER"),
        ("refund_amount", "DECIMAL(12,2)"),
    ), ()),
    ("invoices", (
        ("invoice_id", "INTEGER PRIMARY KEY"),
        ("order_id", "INTEGER REFERENCES orders"),
        ("invoice_date", "DATE"),
        ("posted_date", "DATE"),
        ("revenue", "DECIMAL(12,2)"),
    ), ()),
    ("partner_sales", (
        ("partner_sale_id", "INTEGER PRIMARY KEY"),
        ("store_id", "INTEGER REFERENCES stores"),
        ("sale_month", "DATE"),
        ("revenue", "DECIMAL(12,2)"),
    ), ()),
    ("fiscal_calendar", (
        ("calendar_date", "DATE PRIMARY KEY"),
        ("fiscal_year", "INTEGER"),
        ("fiscal_quarter", "INTEGER"),
        ("fiscal_month", "INTEGER"),
        ("fiscal_week_start", "DATE"),
        ("is_quarter_end", "BOOLEAN"),
    ), ()),
    ("targets", (
        ("target_id", "INTEGER PRIMARY KEY"),
        ("store_id", "INTEGER REFERENCES stores"),
        ("fiscal_year", "INTEGER"),
        ("fiscal_quarter", "INTEGER"),
        ("target_revenue", "DECIMAL(14,2)"),
    ), ()),
    ("commission_earned", (
        ("earned_id", "INTEGER PRIMARY KEY"),
        ("rep_id", "INTEGER REFERENCES sales_reps"),
        ("fiscal_year", "INTEGER"),
        ("fiscal_month", "INTEGER"),
        ("earned_amount", "DECIMAL(12,2)"),
    ), ()),
    ("commission_paid", (
        ("paid_id", "INTEGER PRIMARY KEY"),
        ("rep_id", "INTEGER REFERENCES sales_reps"),
        ("paid_date", "DATE"),
        ("fiscal_year", "INTEGER"),
        ("fiscal_month", "INTEGER"),
        ("paid_amount", "DECIMAL(12,2)"),
    ), ()),
    ("app_users", (
        ("user_id", "INTEGER PRIMARY KEY"),
        ("display_name", "VARCHAR"),
        ("role", "VARCHAR"),
        ("region_scope", "VARCHAR"),
    ), ()),
    ("finance_closed_totals", (
        ("fiscal_year", "INTEGER"),
        ("fiscal_quarter", "INTEGER"),
        ("region", "VARCHAR"),
        ("net_revenue", "DECIMAL(14,2)"),
        ("closed_on", "DATE"),
    ), ("PRIMARY KEY (fiscal_year, fiscal_quarter, region)",)),
    ("data_loads", (
        ("table_name", "VARCHAR PRIMARY KEY"),
        ("loaded_through", "DATE"),
    ), ()),
)

TABLE_NAMES = tuple(name for name, _, _ in TABLES)


def create_sql(name, columns, constraints=()):
    parts = [f"{column} {sql_type}" for column, sql_type in columns]
    parts += list(constraints)
    body = ",\n    ".join(parts)
    return f"CREATE TABLE {name} (\n    {body}\n)"


def write_csv(path, columns, rows):
    # The csv module writes None as an empty field, and DuckDB reads
    # an empty field as NULL. Dates print as YYYY-MM-DD.
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(column for column, _ in columns)
        writer.writerows(rows)


def load_table(con, folder, name, columns, constraints, rows):
    path = Path(folder) / f"{name}.csv"
    write_csv(path, columns, rows)
    con.execute(create_sql(name, columns, constraints))
    # Forward slashes work on every OS, and quotes are doubled so a
    # folder name with an apostrophe can't break the SQL.
    source = path.as_posix().replace("'", "''")
    con.execute(f"COPY {name} FROM '{source}' (FORMAT csv, HEADER true)")


def load_database(db_path, tables, noise=()):
    """Build the database at db_path from generated rows.

    We build into a temporary file next to the target and swap it in
    at the end, so a failed build never leaves a half-made database
    where the old one was.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    building = db_path.with_name(f"{db_path.stem}.building.duckdb")
    for leftover in (building, Path(f"{building}.wal")):
        leftover.unlink(missing_ok=True)

    con = duckdb.connect(str(building))
    try:
        # The build prints its own summary. A progress bar per COPY
        # would just be noise in the terminal.
        con.execute("SET enable_progress_bar = false")
        with tempfile.TemporaryDirectory(prefix="kora-") as folder:
            for name, columns, constraints in TABLES:
                load_table(con, folder, name, columns, constraints,
                           tables[name])
            for name, columns, rows in noise:
                # The first noise column is always its id.
                keyed = ((columns[0][0], "INTEGER PRIMARY KEY"),
                         *columns[1:])
                load_table(con, folder, name, keyed, (), rows)
        con.execute("CHECKPOINT")
    finally:
        con.close()

    for old in (db_path, Path(f"{db_path}.wal")):
        old.unlink(missing_ok=True)
    os.replace(building, db_path)


def export_parquet(db_path, folder):
    """Write every table in the database to folder/<table>.parquet."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    # Clear old files first, so noise tables from an earlier build
    # don't hang around next to a clean export.
    for old in sorted(folder.glob("*.parquet")):
        old.unlink()
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for name in table_names(con):
            target = (folder / f"{name}.parquet").as_posix()
            target = target.replace("'", "''")
            con.execute(f"COPY {name} TO '{target}' (FORMAT parquet)")
    finally:
        con.close()


def table_names(con):
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' ORDER BY table_name"
    ).fetchall()
    return [name for (name,) in rows]


def row_counts(db_path):
    """{table: row count} for every table, core tables first."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        names = table_names(con)
        ordered = [n for n in TABLE_NAMES if n in names]
        ordered += [n for n in names if n not in TABLE_NAMES]
        return {
            name: con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            for name in ordered
        }
    finally:
        con.close()
