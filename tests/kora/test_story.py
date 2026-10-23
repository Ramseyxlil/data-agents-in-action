"""The numbers chapter 1 tells a story about must land where it needs."""

import json

import pytest

from kora import numbers


@pytest.fixture(scope="module")
def found(kora_db):
    return numbers.compute(kora_db.con)


def test_north_week_drops_about_six_percent(found):
    """Chapter 1.1: the week-on-week drop Amara asks about."""
    assert -6.5 <= found["north_week_change_pct"] <= -5.5


def test_north_q1_lands_two_to_four_percent_under_target(found):
    """Chapter 1.3: North missed its FY2027 Q1 target, but not by much."""
    assert -4.0 <= found["north_fy2027q1_vs_target_pct"] <= -2.0


def test_listing_1_1_overstates_finance(found):
    """Chapter 1.2: the wrong query must be visibly wrong."""
    assert found["finance_north_fy2027q1"] == found["north_fy2027q1_net"]
    assert found["listing_1_1_vs_finance_pct"] >= 5.0


def test_three_revenues_are_at_least_three_percent_apart(found):
    """Chapter 1: the three totals must be clearly different numbers."""
    totals = sorted([
        found["north_fy2024_orders_revenue"],
        found["north_fy2024_invoices_revenue"],
        found["north_fy2024_partner_revenue"],
    ])
    for low, high in zip(totals, totals[1:]):
        assert (high - low) / low >= 0.03


def test_numbers_json_matches_the_data(found):
    """The numbers the chapter quotes must match a fresh build."""
    saved = json.loads(numbers.NUMBERS_JSON.read_text(encoding="utf-8"))
    assert saved == found
