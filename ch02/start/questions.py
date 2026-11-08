"""The questions for the section 2.5 experiment, with their right answers.

Every expected value comes from running truth_sql against Kora's
database. None is typed in by hand. The truth SQL uses the meanings
finance uses: fiscal years named after the year they end in, Q1 is May
to July, and revenue means net invoiced revenue (invoices.revenue).
The one exception is the weekly question, which follows how
ch01/numbers.json defines a week (see why_hard).
"""

import json
from dataclasses import dataclass
from pathlib import Path

import duckdb

NUMBERS_JSON = Path(__file__).resolve().parents[2] / "ch01" / "numbers.json"


@dataclass(frozen=True)
class Alternate:
    """Another correct way to answer, like a dollar gap for a percent."""

    label: str
    truth_sql: str
    kind: str


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    level: str
    truth_sql: str
    # "money", "count" or "percent". The kind decides how close the
    # agent's number must be. See TOLERANCES below.
    kind: str
    why_hard: str | None = None
    # Some questions have more than one right answer. "How did North do
    # against target?" is answered just as well by "$49k short" as by
    # "3% short". Each alternate has its own truth SQL and kind.
    alternates: tuple[Alternate, ...] = ()


# How far off an answer may be and still pass, by kind. Money must be
# right to the cent, counts exactly. Percent answers get 0.05
# percentage points, so -6.04 passes for -6.0 but -6.1 does not.
TOLERANCES = {"money": 0.005, "count": 0, "percent": 0.05}


NORTH_NET_FY2027_Q1 = """
SELECT SUM(i.revenue) AS net_revenue
FROM invoices i
JOIN orders o ON i.order_id = o.order_id
JOIN stores s ON o.store_id = s.store_id
JOIN fiscal_calendar c ON i.invoice_date = c.calendar_date
WHERE s.region = 'North'
  AND c.fiscal_year = 2027 AND c.fiscal_quarter = 1
"""

# North's net revenue and target for FY2027 Q1, side by side. h2's
# percent answer and its dollar answer both start from this.
NORTH_VS_TARGET_FY2027_Q1 = f"""
WITH actual AS ({NORTH_NET_FY2027_Q1}),
goal AS (
    SELECT SUM(t.target_revenue) AS target_revenue
    FROM targets t
    JOIN stores s ON t.store_id = s.store_id
    WHERE s.region = 'North'
      AND t.fiscal_year = 2027 AND t.fiscal_quarter = 1
)"""

QUESTIONS = [
    Question(
        id="e1", level="easy", kind="count",
        question="How many stores are in the North region?",
        truth_sql="SELECT COUNT(*) FROM stores WHERE region = 'North'"),
    Question(
        id="e2", level="easy", kind="count",
        question="How many warehouses does Kora have?",
        truth_sql="SELECT COUNT(*) FROM warehouses"),
    Question(
        id="e3", level="easy", kind="count",
        question="How many products does Kora sell?",
        truth_sql="SELECT COUNT(*) FROM products"),
    Question(
        id="e4", level="easy", kind="count",
        question="How many orders were placed on 14 February 2026?",
        truth_sql="""
SELECT COUNT(*) FROM orders WHERE order_date = DATE '2026-02-14'
"""),
    Question(
        id="m1", level="medium", kind="count",
        question="How many orders were cancelled in calendar year 2025?",
        truth_sql="""
SELECT COUNT(*) FROM orders
WHERE status = 'cancelled'
  AND order_date >= DATE '2025-01-01'
  AND order_date <  DATE '2026-01-01'
"""),
    Question(
        id="m2", level="medium", kind="money",
        question="How much did we refund on returns processed in "
                 "July 2026?",
        truth_sql="""
SELECT SUM(refund_amount) FROM returns
WHERE return_date >= DATE '2026-07-01'
  AND return_date <  DATE '2026-08-01'
"""),
    Question(
        id="m3", level="medium", kind="count",
        question="How many new customer accounts were created in 2025?",
        truth_sql="""
SELECT COUNT(*) FROM customers
WHERE created_on >= DATE '2025-01-01'
  AND created_on <  DATE '2026-01-01'
"""),
    Question(
        id="m4", level="medium", kind="money",
        question="How much commission did we pay sales reps in 2025?",
        truth_sql="""
SELECT SUM(paid_amount) FROM commission_paid
WHERE paid_date >= DATE '2025-01-01'
  AND paid_date <  DATE '2026-01-01'
"""),
    Question(
        id="h1", level="hard", kind="money",
        question="What was North's revenue last quarter?",
        why_hard="Kora's quarters are fiscal (last quarter is May to "
                 "July 2026), and finance counts net invoiced revenue, "
                 "not orders.revenue.",
        truth_sql=NORTH_NET_FY2027_Q1),
    Question(
        id="h2", level="hard", kind="percent",
        question="How did North do against target last quarter?",
        why_hard="Targets are per store per fiscal quarter, and they "
                 "are set on net revenue. Gross orders or calendar "
                 "months give a different gap.",
        truth_sql=NORTH_VS_TARGET_FY2027_Q1 + """
SELECT (net_revenue - target_revenue) / target_revenue * 100
FROM actual, goal
""",
        alternates=(
            Alternate(
                label="dollar gap", kind="money",
                truth_sql=NORTH_VS_TARGET_FY2027_Q1 + """
SELECT net_revenue - target_revenue
FROM actual, goal
"""),
            # "North hit 97% of target" says the same thing again.
            Alternate(
                label="attainment", kind="percent",
                truth_sql=NORTH_VS_TARGET_FY2027_Q1 + """
SELECT net_revenue / target_revenue * 100
FROM actual, goal
"""),
        )),
    Question(
        id="h3", level="hard", kind="money",
        question="What was North's revenue in FY2024?",
        why_hard="Three tables have a revenue column. Finance means "
                 "invoices, and FY2024 runs May 2023 to April 2024.",
        truth_sql="""
SELECT SUM(i.revenue)
FROM invoices i
JOIN orders o ON i.order_id = o.order_id
JOIN stores s ON o.store_id = s.store_id
JOIN fiscal_calendar c ON i.invoice_date = c.calendar_date
WHERE s.region = 'North' AND c.fiscal_year = 2024
"""),
    Question(
        id="h4", level="hard", kind="percent",
        question="How did North's revenue change last week?",
        why_hard="Invoices are only loaded through 6 August, so last "
                 "week looks far worse in invoices. The week runs "
                 "Monday to Sunday and the weekly figure is completed "
                 "orders, as in ch01/numbers.json.",
        truth_sql="""
WITH weeks AS (
    SELECT
        SUM(o.revenue) FILTER (WHERE o.order_date
            BETWEEN DATE '2026-08-03' AND DATE '2026-08-09') AS last,
        SUM(o.revenue) FILTER (WHERE o.order_date
            BETWEEN DATE '2026-07-27' AND DATE '2026-08-02') AS prev
    FROM orders o
    JOIN stores s ON o.store_id = s.store_id
    WHERE s.region = 'North' AND o.status = 'completed'
)
SELECT (last - prev) / prev * 100 FROM weeks
"""),
]

# The hard questions must agree with what chapter 1 already printed.
NUMBERS_KEYS = {
    "h1": ("north_fy2027q1_net", 2),
    "h2": ("north_fy2027q1_vs_target_pct", 1),
    "h3": ("north_fy2024_invoices_revenue", 2),
    "h4": ("north_week_change_pct", 1),
}

# Alternates are checked too. numbers.json has no dollar gap or
# attainment, so each is worked out from the keys it does have.
def north_q1_dollar_gap(numbers):
    """North's FY2027 Q1 net minus its target, from numbers.json."""
    net = numbers["north_fy2027q1_net"]
    return net - numbers["north_fy2027q1_target"]


def north_q1_attainment(numbers):
    """North's FY2027 Q1 net as a percent of target."""
    net = numbers["north_fy2027q1_net"]
    return net / numbers["north_fy2027q1_target"] * 100


# (question id, alternate label) -> (decimal places, how to work the
# value out from numbers.json)
NUMBERS_ALTERNATES = {
    ("h2", "dollar gap"): (2, north_q1_dollar_gap),
    ("h2", "attainment"): (1, north_q1_attainment),
}


def run_truth(truth_sql, db_path):
    """Run one piece of truth SQL and return its answer as a float."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        (value,) = con.execute(truth_sql).fetchone()
    finally:
        con.close()
    return float(value)


def expected_value(question, db_path):
    """The question's main right answer, from its truth SQL."""
    return run_truth(question.truth_sql, db_path)


def accepted_answers(question, db_path):
    """Every right answer as (kind, value): the main one first."""
    answers = [(question.kind, expected_value(question, db_path))]
    for alternate in question.alternates:
        value = run_truth(alternate.truth_sql, db_path)
        answers.append((alternate.kind, value))
    return answers


def check_against_numbers(db_path):
    """List hard questions whose truth SQL disagrees with numbers.json."""
    numbers = json.loads(NUMBERS_JSON.read_text(encoding="utf-8"))
    problems = []
    for question in QUESTIONS:
        if question.id not in NUMBERS_KEYS:
            continue
        key, digits = NUMBERS_KEYS[question.id]
        found = round(expected_value(question, db_path), digits)
        if found != numbers[key]:
            problems.append(f"{question.id}: truth SQL gives {found}, "
                            f"numbers.json {key} says {numbers[key]}")

    by_id = {question.id: question for question in QUESTIONS}
    for (question_id, label), check in NUMBERS_ALTERNATES.items():
        digits, work_out = check
        wanted = round(work_out(numbers), digits)
        alternate = next(a for a in by_id[question_id].alternates
                         if a.label == label)
        found = round(run_truth(alternate.truth_sql, db_path), digits)
        if found != wanted:
            problems.append(f"{question_id} {label}: truth SQL gives "
                            f"{found}, numbers.json gives {wanted}")
    return problems
