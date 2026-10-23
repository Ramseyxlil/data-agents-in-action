"""The four story numbers the book quotes, built into the data on purpose.

The generator makes ordinary, noisy retail data. Left alone, the noise
would decide what chapter 1 says. The rules in this file make sure the
numbers the book tells a story about come out the way the story needs,
every time, from the generator itself. Nothing here is patched into
the database afterward, and the tests never hard-code the results.
"""

from datetime import date

# ------------------------------------------------------------------
# Story 1, chapter 1.1: North's revenue drops about 6% in a week.
# ------------------------------------------------------------------
# The cause is something a good analyst can find: one large North
# business customer orders every Wednesday, then doesn't order in the
# last week of data. Everything else in North stays roughly flat, so
# the drop has one clear "why" for the agent to dig out later.

NORTH_WEEK_PREV = (date(2026, 7, 27), date(2026, 8, 2))
NORTH_WEEK_LAST = (date(2026, 8, 3), date(2026, 8, 9))

# Aim for the middle of the 5.5% to 6.5% range the book needs.
NORTH_WEEK_DROP_PCT = 6

# "Roughly flat" means the rest of North moves less than 1%.
FLAT_TOLERANCE = 0.01
MAX_FLAT_ATTEMPTS = 500

BIG_CUSTOMER_STORE_ID = 1
BIG_CUSTOMER_SINCE = date(2021, 3, 8)
BIG_CUSTOMER_WEEKDAY = 2
# Each weekly order is worth about this share of North's other sales
# that week, so the customer stays "large" as Kora grows.
BIG_CUSTOMER_SHARE = 0.064


def others_are_flat(prev_cents, last_cents):
    """True when North without the big customer barely moved."""
    return abs(last_cents / prev_cents - 1) <= FLAT_TOLERANCE


def big_customer_weekly_value(others_cents, rng):
    # A bit of wobble week to week, so the orders look real.
    wobble = 0.9 + 0.2 * rng.random()
    return int(others_cents * BIG_CUSTOMER_SHARE * wobble)


def big_customer_last_order_value(prev_others, last_others):
    """Size the customer's final order so the week-on-week drop lands
    on NORTH_WEEK_DROP_PCT.

    We want last / (prev + order) = 1 - drop. Solving for the order
    gives the value below, rounded up to a whole cent.
    """
    keep = 100 - NORTH_WEEK_DROP_PCT
    needed = -(-last_others * 100 // keep)
    return needed - prev_others


# ------------------------------------------------------------------
# Story 2, chapter 1.3: North finishes FY2027 Q1 about 3% under target.
# ------------------------------------------------------------------
# Targets come from a plan, not from actuals. For this one quarter we
# set North's targets so the region lands 3% short, which is the gap
# Amara asks the agent to explain.

NORTH_Q1 = (2027, 1)
NORTH_Q1_SHORTFALL_PCT = 3


def north_q1_targets(net_cents, plans):
    """Scale North's planned targets so net / target = 0.97.

    The plan still decides how the target splits across stores. Only
    the region total is pinned.
    """
    total = net_cents * 100 // (100 - NORTH_Q1_SHORTFALL_PCT)
    plan_sum = sum(plans)
    targets = [plan * total // plan_sum for plan in plans]
    # Integer division drops a few cents. Give them to the last store
    # so the region total is exact.
    targets[-1] += total - sum(targets)
    return targets


# ------------------------------------------------------------------
# Story 3, chapters 1.2 and 2: the wrong revenue column.
# ------------------------------------------------------------------
# Listing 1.1 sums orders.revenue for April to June. That is wrong
# twice: it is gross (cancelled orders and refunds still in) and it
# uses calendar months, not fiscal Q1 (May to July). The gap comes from
# config.CANCEL_RATE, the return rates, and the spring bump in
# config.MONTH_FACTORS that makes April bigger than July. Together they
# put the wrong answer well over 5% above finance's number.

# ------------------------------------------------------------------
# Story 4, chapters 1 and 5: three columns called revenue.
# ------------------------------------------------------------------
# orders.revenue is gross, invoices.revenue is net. partner_sales
# carries the reseller's own adjusted figure, which runs 6% to 10%
# above the store's gross orders for the month. So the three totals
# for the same region and year never agree.

PARTNER_UPLIFT_PERMILLE = (1060, 1100)


def partner_revenue(gross_cents, rng):
    return gross_cents * rng.randint(*PARTNER_UPLIFT_PERMILLE) // 1000
