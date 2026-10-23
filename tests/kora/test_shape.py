"""Shape and sanity checks. If these fail, nothing else can be trusted."""

from datetime import date

import pytest

EXPECTED_COLUMNS = {
    "regions": ["region_id", "region_name"],
    "warehouses": ["warehouse_id", "warehouse_name", "region"],
    "stores": ["store_id", "store_name", "region", "warehouse_id",
               "city", "opened_on", "closed_on", "is_active"],
    "products": ["product_id", "sku", "product_name", "category",
                 "description", "unit_price", "unit_cost"],
    "customers": ["customer_id", "customer_type", "home_store_id",
                  "created_on"],
    "sales_reps": ["rep_id", "rep_code", "store_id", "region",
                   "hired_on"],
    "orders": ["order_id", "order_date", "store_id", "customer_id",
               "rep_id", "channel", "status", "revenue"],
    "order_lines": ["order_line_id", "order_id", "product_id",
                    "quantity", "unit_price", "discount_amount",
                    "line_amount"],
    "returns": ["return_id", "order_id", "order_line_id",
                "return_date", "quantity", "refund_amount"],
    "invoices": ["invoice_id", "order_id", "invoice_date",
                 "posted_date", "revenue"],
    "partner_sales": ["partner_sale_id", "store_id", "sale_month",
                      "revenue"],
    "fiscal_calendar": ["calendar_date", "fiscal_year",
                        "fiscal_quarter", "fiscal_month",
                        "fiscal_week_start", "is_quarter_end"],
    "targets": ["target_id", "store_id", "fiscal_year",
                "fiscal_quarter", "target_revenue"],
    "commission_earned": ["earned_id", "rep_id", "fiscal_year",
                          "fiscal_month", "earned_amount"],
    "commission_paid": ["paid_id", "rep_id", "paid_date",
                        "fiscal_year", "fiscal_month", "paid_amount"],
    "app_users": ["user_id", "display_name", "role", "region_scope"],
    "finance_closed_totals": ["fiscal_year", "fiscal_quarter", "region",
                              "net_revenue", "closed_on"],
    "data_loads": ["table_name", "loaded_through"],
}


def test_tables_have_exactly_the_spec_columns(kora_db):
    """The book quotes these names, so they must not drift."""
    rows = kora_db.all(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' "
        "ORDER BY table_name, ordinal_position"
    )
    found = {}
    for table, column in rows:
        found.setdefault(table, []).append(column)
    assert found == EXPECTED_COLUMNS


def test_orders_stay_inside_the_data_window(kora_db):
    """Readers are told the data runs 2023-05-01 to 2026-08-09."""
    first, last = kora_db.all(
        "SELECT min(order_date), max(order_date) FROM orders"
    )[0]
    assert first >= date(2023, 5, 1)
    assert last <= date(2026, 8, 9)


@pytest.mark.parametrize("sql", [
    "SELECT count(*) FROM order_lines WHERE quantity <= 0",
    "SELECT count(*) FROM order_lines WHERE unit_price < 0",
    "SELECT count(*) FROM order_lines WHERE discount_amount < 0",
    "SELECT count(*) FROM order_lines WHERE line_amount < 0",
    "SELECT count(*) FROM products WHERE unit_price < 0",
    "SELECT count(*) FROM products WHERE unit_cost < 0",
    "SELECT count(*) FROM returns WHERE quantity <= 0",
    "SELECT count(*) FROM returns WHERE refund_amount < 0",
])
def test_no_negative_amounts(kora_db, sql):
    """Negative prices or refunds would be a generator bug, not a trap."""
    assert kora_db.one(sql) == 0


def test_orders_point_to_real_rows(kora_db):
    """A dangling ID would break joins the book relies on."""
    missing = kora_db.one("""
        SELECT count(*) FROM orders o
        LEFT JOIN stores s ON o.store_id = s.store_id
        LEFT JOIN customers c ON o.customer_id = c.customer_id
        LEFT JOIN sales_reps r ON o.rep_id = r.rep_id
        WHERE s.store_id IS NULL OR c.customer_id IS NULL
           OR r.rep_id IS NULL
    """)
    assert missing == 0


def test_returns_point_to_a_line_on_the_same_order(kora_db):
    """A return must belong to one real line of its own order."""
    bad = kora_db.one("""
        SELECT count(*) FROM returns r
        LEFT JOIN order_lines l ON r.order_line_id = l.order_line_id
        WHERE l.order_line_id IS NULL OR l.order_id <> r.order_id
           OR r.quantity > l.quantity
    """)
    assert bad == 0


def test_cancelled_orders_have_no_invoice(kora_db):
    """Finance never bills a cancelled order."""
    assert kora_db.one("""
        SELECT count(*) FROM invoices i
        JOIN orders o ON i.order_id = o.order_id
        WHERE o.status = 'cancelled'
    """) == 0


def test_completed_orders_have_one_invoice_unless_not_loaded(kora_db):
    """Only invoices not yet loaded may be missing, and none doubled."""
    loaded = kora_db.one(
        "SELECT loaded_through FROM data_loads "
        "WHERE table_name = 'invoices'"
    )
    assert kora_db.one("""
        SELECT count(*) FROM (
            SELECT order_id FROM invoices
            GROUP BY order_id HAVING count(*) > 1
        )
    """) == 0
    assert kora_db.one(
        "SELECT count(*) FROM invoices WHERE posted_date > ?", loaded
    ) == 0
    # Posting is at most 6 days late, so a missing invoice can only
    # belong to an order from the last 6 days before loaded_through.
    oldest_missing = kora_db.one("""
        SELECT min(o.order_date) FROM orders o
        LEFT JOIN invoices i ON o.order_id = i.order_id
        WHERE o.status = 'completed' AND i.invoice_id IS NULL
    """)
    assert (loaded - oldest_missing).days < 7


@pytest.mark.parametrize("day, year, quarter, month", [
    (date(2023, 5, 1), 2024, 1, 1),
    (date(2024, 4, 30), 2024, 4, 12),
    (date(2026, 8, 10), 2027, 2, 4),
])
def test_fiscal_calendar_labels(kora_db, day, year, quarter, month):
    """Fiscal years start in May and are named after the end year."""
    row = kora_db.all(
        "SELECT fiscal_year, fiscal_quarter, fiscal_month "
        "FROM fiscal_calendar WHERE calendar_date = ?", day
    )
    assert row == [(year, quarter, month)]


def test_fiscal_calendar_covers_every_day(kora_db):
    """Joins to the calendar must never drop a day."""
    first, last, days = kora_db.all(
        "SELECT min(calendar_date), max(calendar_date), count(*) "
        "FROM fiscal_calendar"
    )[0]
    assert first == date(2023, 5, 1)
    assert last == date(2027, 4, 30)
    assert days == (last - first).days + 1


def test_finance_totals_match_the_invoices(kora_db):
    """Finance's closed numbers are the reconciliation target."""
    mismatches = kora_db.all("""
        WITH inv AS (
            SELECT c.fiscal_year, c.fiscal_quarter, s.region,
                   round(sum(i.revenue), 2) AS net
            FROM invoices i
            JOIN orders o ON i.order_id = o.order_id
            JOIN stores s ON o.store_id = s.store_id
            JOIN fiscal_calendar c ON i.invoice_date = c.calendar_date
            GROUP BY ALL
        )
        SELECT f.* FROM finance_closed_totals f
        LEFT JOIN inv USING (fiscal_year, fiscal_quarter, region)
        WHERE inv.net IS DISTINCT FROM f.net_revenue
    """)
    assert mismatches == []
    assert kora_db.one("SELECT count(*) FROM finance_closed_totals") > 0
