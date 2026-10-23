"""Each trap the book teaches must really be in the data.

If a refactor quietly removes one, a chapter's lesson stops working,
and these tests are the only thing that would notice.
"""

from datetime import date

from kora import config, numbers


def test_three_revenue_columns_disagree(kora_db):
    """Chapters 1 and 5: same region and year, three different totals."""
    found = numbers.compute(kora_db.con)
    totals = {
        found["north_fy2024_orders_revenue"],
        found["north_fy2024_invoices_revenue"],
        found["north_fy2024_partner_revenue"],
    }
    assert len(totals) == 3


def test_returns_joined_on_order_id_double_count(kora_db):
    """Chapter 4: the wrong join runs clean and overstates refunds."""
    right = kora_db.one("""
        SELECT sum(r.refund_amount) FROM returns r
        JOIN order_lines l ON r.order_line_id = l.order_line_id
    """)
    wrong = kora_db.one("""
        SELECT sum(r.refund_amount) FROM returns r
        JOIN order_lines l ON r.order_id = l.order_id
    """)
    assert wrong > right


def test_closed_east_store_still_looks_active(kora_db):
    """Chapters 4 and 8: closed, but is_active and targets say no."""
    closed = kora_db.all(
        "SELECT store_id, closed_on, is_active FROM stores "
        "WHERE region = 'East' AND closed_on IS NOT NULL"
    )
    assert len(closed) == 1
    store_id, closed_on, is_active = closed[0]
    assert closed_on == date(2025, 3, 31)
    assert is_active is True
    assert kora_db.one(
        "SELECT count(*) FROM orders "
        "WHERE store_id = ? AND order_date > ?", store_id, closed_on
    ) == 0
    late_targets = kora_db.one("""
        SELECT count(*) FROM targets t
        JOIN fiscal_calendar c
          ON c.fiscal_year = t.fiscal_year
         AND c.fiscal_quarter = t.fiscal_quarter
         AND c.fiscal_month % 3 = 1
        WHERE t.store_id = ? AND c.calendar_date > ?
    """, store_id, closed_on)
    assert late_targets > 0


def test_some_invoices_post_in_the_next_quarter(kora_db):
    """Chapters 1 and 10: grouping by posted_date moves revenue."""
    assert kora_db.one("""
        SELECT count(*) FROM invoices i
        JOIN fiscal_calendar a ON i.invoice_date = a.calendar_date
        JOIN fiscal_calendar b ON i.posted_date = b.calendar_date
        WHERE a.fiscal_year <> b.fiscal_year
           OR a.fiscal_quarter <> b.fiscal_quarter
    """) > 0


def test_invoices_load_behind_other_tables(kora_db):
    """Chapters 1 and 10: only data_loads says invoices are behind."""
    loads = dict(kora_db.all("SELECT * FROM data_loads"))
    invoices = loads.pop("invoices")
    assert invoices == date(2026, 8, 6)
    assert set(loads.values()) == {date(2026, 8, 9)}


def test_north_region_and_north_warehouse_differ(kora_db):
    """Chapter 5: "region" names a sales region and a warehouse group."""
    sales_north = {row[0] for row in kora_db.all(
        "SELECT store_id FROM stores WHERE region = 'North'"
    )}
    warehouse_north = {row[0] for row in kora_db.all("""
        SELECT s.store_id FROM stores s
        JOIN warehouses w ON s.warehouse_id = w.warehouse_id
        WHERE w.region = 'North'
    """)}
    assert len(sales_north - warehouse_north) >= 3
    assert len(warehouse_north - sales_north) >= 2


def test_commission_paid_differs_from_earned(kora_db):
    """Chapter 6: paid in FY2027 Q1 is mostly last year's money."""
    earned = kora_db.one("""
        SELECT sum(earned_amount) FROM commission_earned
        WHERE fiscal_year = 2027 AND fiscal_month BETWEEN 1 AND 3
    """)
    paid = kora_db.one("""
        SELECT sum(paid_amount) FROM commission_paid
        WHERE paid_date BETWEEN '2026-05-01' AND '2026-07-31'
    """)
    assert abs(paid - earned) / earned > 0.20


def test_exactly_one_product_carries_the_injection(kora_db):
    """Chapter 9: one hidden instruction, in one product description."""
    rows = kora_db.all(
        "SELECT description FROM products WHERE description LIKE ?",
        "%" + config.INJECTION_SENTENCE + "%",
    )
    assert len(rows) == 1
    assert rows[0][0].endswith(config.INJECTION_SENTENCE)


def test_app_users_are_the_four_fictional_users(kora_db):
    """Chapters 3 and 9: who asks changes the right answer."""
    rows = kora_db.all("SELECT * FROM app_users ORDER BY user_id")
    assert rows == [
        (1, "Amara", "regional_manager", "North"),
        (2, "Tomas", "regional_manager", "West"),
        (3, "Grace", "finance", "ALL"),
        (4, "Dayo", "analyst", "ALL"),
    ]
