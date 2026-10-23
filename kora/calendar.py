"""Kora's fiscal calendar rules, in one place.

The fiscal year starts on 1 May and is named after the year it ends
in. Q1 is May to July, Q2 August to October, Q3 November to January
and Q4 February to April. Fiscal weeks run Monday to Sunday.
"""

from datetime import date, timedelta
from functools import lru_cache

from kora.config import FISCAL_YEAR_START_MONTH as FIRST_MONTH


# These get called for every order, so caching saves real time.
@lru_cache(maxsize=None)
def fiscal_year(day):
    return day.year + 1 if day.month >= FIRST_MONTH else day.year


@lru_cache(maxsize=None)
def fiscal_month(day):
    # May is fiscal month 1, April is fiscal month 12.
    return (day.month - FIRST_MONTH) % 12 + 1


def fiscal_quarter(day):
    return (fiscal_month(day) - 1) // 3 + 1


def quarter_of(day):
    return fiscal_year(day), fiscal_quarter(day)


def week_start(day):
    # Monday of the week the day falls in.
    return day - timedelta(days=day.weekday())


def fiscal_month_start(year, month):
    """First calendar day of a fiscal month."""
    offset = FIRST_MONTH - 1 + month - 1
    return date(year - 1 + offset // 12, offset % 12 + 1, 1)


def add_months(day, months):
    offset = day.month - 1 + months
    return date(day.year + offset // 12, offset % 12 + 1, day.day)


def quarter_start(year, quarter):
    return fiscal_month_start(year, (quarter - 1) * 3 + 1)


def quarter_end(year, quarter):
    first = quarter_start(year, quarter)
    return add_months(first, 3) - timedelta(days=1)


def is_quarter_end(day):
    return day == quarter_end(*quarter_of(day))


def days_to_quarter_end(day):
    return (quarter_end(*quarter_of(day)) - day).days


def quarters(first, last):
    """Every (fiscal_year, fiscal_quarter) from first to last."""
    year, quarter = first
    while (year, quarter) <= last:
        yield year, quarter
        quarter += 1
        if quarter == 5:
            year, quarter = year + 1, 1


def date_range(first, last):
    """Every day from first to last, both included."""
    for offset in range((last - first).days + 1):
        yield first + timedelta(days=offset)


def add_business_days(day, count):
    # Weekends don't count. Kora's finance team doesn't close on them.
    while count:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count -= 1
    return day
