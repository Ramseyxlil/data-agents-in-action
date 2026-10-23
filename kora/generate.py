"""Build every Kora table as plain Python rows, in dependency order.

Nothing in this file touches DuckDB. Each table comes out as a list of
tuples in the column order kora/load.py expects. Money stays in whole
cents until a row is written, so every sum is exact and every machine
gets the same answer.
"""

import bisect
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import accumulate
from random import Random

from kora import calendar as cal
from kora import config, story


def child_rng(seed, *labels):
    # Every part of the data gets its own random stream, named after
    # what it builds. When the story code regenerates one North week,
    # nothing else in the dataset moves. String seeds are hashed with
    # SHA-512 by Python, so they give the same stream on any machine.
    return Random(":".join(str(part) for part in (seed, *labels)))


def money(cents):
    # Cents become "12.34" only at the very end.
    return f"{cents // 100}.{cents % 100:02d}"


def random_day(rng, first, last):
    return first + timedelta(days=rng.randint(0, (last - first).days))


@dataclass(frozen=True)
class Store:
    store_id: int
    name: str
    region: str
    warehouse_id: int
    city: str | None
    opened_on: date
    closed_on: date | None
    weight: float

    @property
    def is_online(self):
        return self.region == config.ONLINE_REGION


@dataclass(frozen=True)
class Product:
    product_id: int
    sku: str
    name: str
    category: str
    description: str
    price: int
    cost: int
    popularity: int


@dataclass(slots=True)
class Draft:
    """One order before it gets an ID.

    Each line is (product_id, quantity, unit_price, discount,
    returned_quantity, days_until_return), all in cents or units.
    """

    day: date
    store_id: int
    customer_id: int
    rep_id: int
    cancelled: bool
    post_delay: int
    lines: list


def line_amount(line):
    return line[1] * line[2] - line[3]


def draft_revenue(draft):
    return sum(line_amount(line) for line in draft.lines)


# ------------------------------------------------------------------
# Stores, products, customers and reps
# ------------------------------------------------------------------


def make_stores(seed):
    rng = child_rng(seed, "stores")
    home_warehouse = {region: wid for wid, _, region in config.WAREHOUSES}
    stores = []
    store_id = 0
    for region, count in config.STORES_PER_REGION:
        cities = config.CITIES[region]
        for n in range(count):
            store_id += 1
            # Draw these for every store, even the special ones, so
            # the random stream stays the same for the stores after.
            opened = random_day(rng, date(2012, 1, 1), date(2022, 12, 31))
            weight = rng.choice(config.STORE_WEIGHTS)
            closed = None
            if store_id == config.NEW_STORE_ID:
                opened = config.NEW_STORE_OPENED_ON
            if store_id == config.CLOSED_STORE_ID:
                closed = config.CLOSED_STORE_ON
            warehouse = config.WAREHOUSE_OVERRIDES.get(
                store_id, home_warehouse[region]
            )
            stores.append(Store(
                store_id=store_id,
                name="Kora " + config.STORE_NAMES[store_id - 1],
                region=region,
                warehouse_id=warehouse,
                city=cities[n % len(cities)],
                opened_on=opened,
                closed_on=closed,
                weight=weight,
            ))

    # The online shop has no town, so its city is left empty.
    stores.append(Store(
        store_id=store_id + 1,
        name=config.ONLINE_STORE_NAME,
        region=config.ONLINE_REGION,
        warehouse_id=config.ONLINE_WAREHOUSE_ID,
        city=None,
        opened_on=date(2019, 3, 1),
        closed_on=None,
        weight=config.ONLINE_WEIGHT,
    ))
    return stores


def make_products(seed):
    rng = child_rng(seed, "products")
    products = []
    for (category, code, count, (low, high), adjectives, nouns,
         blurbs) in config.CATEGORIES:
        names = [f"{adj} {noun}" for noun in nouns for adj in adjectives]
        for n, name in enumerate(rng.sample(names, count), start=1):
            product_id = len(products) + 1
            # Prices end in .99, like most shelf prices do.
            price = rng.randint(low, high) * 100 + 99
            cost = price * rng.randint(45, 68) // 100
            description = " ".join(rng.sample(blurbs, 2))
            if product_id == config.INJECTION_PRODUCT_ID:
                # Chapter 9: the hidden instruction sits at the end of
                # an otherwise normal description.
                description += " " + config.INJECTION_SENTENCE
            products.append(Product(
                product_id=product_id,
                sku=f"KOR-{code}-{n:04d}",
                name=name,
                category=category,
                description=description,
                price=price,
                cost=cost,
                popularity=rng.choice((1, 1, 2, 2, 3, 5, 8)),
            ))
    return products


def signup_day(rng, store, n):
    last = store.closed_on or config.END
    if store.opened_on > config.START:
        # A store that opens inside the window has no older customers.
        # The first few sign up on opening day so the store can trade.
        if n < 40:
            return store.opened_on
        return random_day(rng, store.opened_on, last)
    # Customer 0 of each kind is always an existing customer, so every
    # store has someone to sell to on day one.
    if n == 0 or rng.random() < config.EXISTING_CUSTOMER_SHARE:
        first = max(store.opened_on, config.EARLIEST_SIGNUP)
        return random_day(rng, first, config.START - timedelta(days=1))
    return random_day(rng, config.START, last)


def make_customers(seed, stores):
    raw = []
    for store in stores:
        rng = child_rng(seed, "customers", store.store_id)
        kinds = (
            ("retail", config.RETAIL_CUSTOMERS_PER_WEIGHT, 50),
            ("business", config.BUSINESS_CUSTOMERS_PER_WEIGHT, 3),
        )
        for kind, per_weight, minimum in kinds:
            count = max(minimum, round(store.weight * per_weight))
            for n in range(count):
                day = signup_day(rng, store, n)
                raw.append((day, store.store_id, kind, n))

    # Story 1: the large North business customer. n = -1 marks it, so
    # it never lands in the pool that ordinary orders pick from.
    raw.append((story.BIG_CUSTOMER_SINCE, story.BIG_CUSTOMER_STORE_ID,
                "business", -1))

    # Customer IDs go up with sign-up date, the way a real CRM hands
    # them out.
    raw.sort()
    rows = []
    pools = {s.store_id: {"retail": ([], []), "business": ([], [])}
             for s in stores}
    big_customer_id = None
    for customer_id, (day, store_id, kind, n) in enumerate(raw, 1):
        rows.append((customer_id, kind, store_id, day))
        if n == -1:
            big_customer_id = customer_id
            continue
        days, ids = pools[store_id][kind]
        days.append(day.toordinal())
        ids.append(customer_id)
    return rows, pools, big_customer_id


def make_reps(seed, stores):
    rows = []
    pools = {}
    per_region = {}
    for store in stores:
        rng = child_rng(seed, "reps", store.store_id)
        last = (store.closed_on or config.END) - timedelta(days=90)
        hires = []
        for n in range(rng.randint(3, 6)):
            if n >= 3:
                # Extra reps join during the window, as stores grow.
                first = config.START + timedelta(days=90)
                hires.append(random_day(rng, first, last))
            elif store.opened_on > config.START:
                gap = rng.randint(7, 45)
                hires.append(store.opened_on - timedelta(days=gap))
            else:
                before = config.START - timedelta(days=1)
                hires.append(random_day(rng, store.opened_on, before))
        hires.sort()

        letter = config.REGION_LETTERS[store.region]
        days, ids = [], []
        for hired in hires:
            rep_id = len(rows) + 1
            per_region[letter] = per_region.get(letter, 0) + 1
            code = f"REP-{letter}-{per_region[letter]:03d}"
            rows.append((rep_id, code, store.store_id, store.region,
                         hired))
            days.append(hired.toordinal())
            ids.append(rep_id)
        pools[store.store_id] = (days, ids)
    return rows, pools


# ------------------------------------------------------------------
# Orders
# ------------------------------------------------------------------


class OrderMaker:
    """Makes the orders for one store on one day."""

    def __init__(self, seed, stores, products, customer_pools,
                 rep_pools):
        self.seed = seed
        self.products = products
        self.popularity = list(accumulate(p.popularity for p in products))
        self.line_counts = [n for n, _ in config.RETAIL_LINE_WEIGHTS]
        self.line_weights = list(
            accumulate(w for _, w in config.RETAIL_LINE_WEIGHTS)
        )
        self.customer_pools = customer_pools
        self.rep_pools = rep_pools

        # Scale the daily rate so the whole window lands near
        # TARGET_ORDERS, whatever the store sizes came out as.
        self.base = 1.0
        total = sum(self.expected(store, day)
                    for store in stores for day in self.open_days(store))
        self.base = config.TARGET_ORDERS / total
        self.total_expected = config.TARGET_ORDERS

    def open_days(self, store):
        first = max(config.START, store.opened_on)
        last = min(config.END, store.closed_on or config.END)
        return cal.date_range(first, last)

    def expected(self, store, day):
        """Average number of orders for this store on this day."""
        years = (day - config.START).days / 365.25
        return (self.base * store.weight
                * config.MONTH_FACTORS[day.month - 1]
                * config.WEEKDAY_FACTORS[day.weekday()]
                * (1 + config.GROWTH_PER_YEAR * years))

    def pick_product(self, rng):
        ticket = rng.randrange(self.popularity[-1])
        return self.products[bisect.bisect_right(self.popularity, ticket)]

    def post_delay(self, rng, day):
        # Chapters 1 and 10: orders in the last 3 days of a fiscal
        # quarter post 3 to 6 days late, so they land in the next
        # quarter if you group by posted_date.
        if cal.days_to_quarter_end(day) < 3:
            return rng.randint(3, 6)
        return rng.randint(0, 2)

    def returned(self, rng, quantity, rate):
        if rng.random() >= rate:
            return 0, 0
        if quantity == 1 or rng.random() < 0.6:
            returned = quantity
        else:
            returned = rng.randint(1, quantity - 1)
        return returned, rng.randint(1, config.MAX_RETURN_DAYS)

    def lines(self, rng, business, cancelled):
        if business:
            count = rng.randint(2, 7)
            rate = config.BUSINESS_RETURN_RATE
        else:
            ticket = rng.randrange(self.line_weights[-1])
            index = bisect.bisect_right(self.line_weights, ticket)
            count = self.line_counts[index]
            rate = config.RETAIL_RETURN_RATE

        lines = []
        seen = set()
        for _ in range(count):
            product = self.pick_product(rng)
            # A second pick of the same product is skipped, because a
            # till puts the same item on one line.
            if product.product_id in seen:
                continue
            seen.add(product.product_id)

            if business:
                quantity = rng.randint(3, 12)
                pct = rng.randint(5, 12) if rng.random() < 0.6 else 0
            else:
                roll = rng.random()
                quantity = (1 if roll < 0.72 else 2 if roll < 0.92
                            else 3 if roll < 0.98 else 4)
                pct = 0
                if rng.random() < 0.15:
                    pct = rng.choice((5, 10, 15, 20))
            discount = quantity * product.price * pct // 100

            returned, delay = 0, 0
            if not cancelled:
                returned, delay = self.returned(rng, quantity, rate)
            lines.append((product.product_id, quantity, product.price,
                          discount, returned, delay))
        return lines

    def store_day(self, store, day, attempt=0):
        rng = child_rng(self.seed, "orders", store.store_id,
                        day.isoformat(), attempt)
        expected = self.expected(store, day)
        count = int(expected)
        if rng.random() < expected - count:
            count += 1

        # Only customers and reps who already exist on this day.
        today = day.toordinal()
        pools = self.customer_pools[store.store_id]
        retail_days, retail_ids = pools["retail"]
        business_days, business_ids = pools["business"]
        n_retail = bisect.bisect_right(retail_days, today)
        n_business = bisect.bisect_right(business_days, today)
        rep_days, rep_ids = self.rep_pools[store.store_id]
        n_reps = bisect.bisect_right(rep_days, today)

        drafts = []
        for _ in range(count):
            business = (n_business > 0
                        and rng.random() < config.BUSINESS_ORDER_SHARE)
            if business:
                customer = business_ids[rng.randrange(n_business)]
            else:
                customer = retail_ids[rng.randrange(n_retail)]
            rep = rep_ids[rng.randrange(n_reps)]
            cancelled = rng.random() < config.CANCEL_RATE
            lines = self.lines(rng, business, cancelled)
            drafts.append(Draft(day, store.store_id, customer, rep,
                                cancelled, self.post_delay(rng, day),
                                lines))
        return drafts

    def bulk_lines(self, rng, value):
        """Lines for one big business order worth exactly value."""
        lines = []
        total = 0
        seen = set()
        while True:
            product = self.pick_product(rng)
            if product.product_id in seen:
                continue
            seen.add(product.product_id)
            quantity = rng.randint(6, 24)
            gross = quantity * product.price
            if total + gross >= value:
                # Last line: just enough units, then a small discount
                # to land on the exact value.
                quantity = -(-(value - total) // product.price)
                gross = quantity * product.price
                discount = total + gross - value
                lines.append((product.product_id, quantity,
                              product.price, discount, 0, 0))
                return lines
            lines.append((product.product_id, quantity, product.price,
                          0, 0, 0))
            total += gross


def north_completed(drafts, north, first, last):
    """Completed-order revenue in cents for North stores, first..last."""
    total = 0
    for day in cal.date_range(first, last):
        for store in north:
            for draft in drafts.get((day, store.store_id), ()):
                if not draft.cancelled:
                    total += draft_revenue(draft)
    return total


def apply_north_week_story(drafts, maker, north):
    """Story 1: keep the rest of North flat across the last two weeks.

    Ordinary noise can move a region's week by several percent. We
    re-roll North's last week (with a new, numbered random stream) until
    it sits within 1% of the week before. Then the big customer's
    missing order is the only real change.
    """
    prev = north_completed(drafts, north, *story.NORTH_WEEK_PREV)
    last_days = list(cal.date_range(*story.NORTH_WEEK_LAST))
    for attempt in range(story.MAX_FLAT_ATTEMPTS):
        candidate = {}
        for day in last_days:
            for store in north:
                key = (day, store.store_id)
                candidate[key] = (maker.store_day(store, day, attempt)
                                  if attempt else drafts[key])
        last = north_completed(candidate, north, *story.NORTH_WEEK_LAST)
        if story.others_are_flat(prev, last):
            drafts.update(candidate)
            return prev, last
    raise RuntimeError("Could not make North's last week flat.")


def add_big_customer_orders(drafts, maker, north, customer_id, rep_id,
                            prev, last):
    """Story 1: the big customer orders every Wednesday, then stops."""
    rng = child_rng(maker.seed, "big-customer")
    monday = cal.week_start(config.START)
    final_monday = story.NORTH_WEEK_PREV[0]
    while monday <= final_monday:
        day = monday + timedelta(days=story.BIG_CUSTOMER_WEEKDAY)
        if monday == final_monday:
            value = story.big_customer_last_order_value(prev, last)
        else:
            others = north_completed(drafts, north, monday,
                                     monday + timedelta(days=6))
            value = story.big_customer_weekly_value(others, rng)
        draft = Draft(day, story.BIG_CUSTOMER_STORE_ID, customer_id,
                      rep_id, False, maker.post_delay(rng, day),
                      maker.bulk_lines(rng, value))
        drafts[(day, story.BIG_CUSTOMER_STORE_ID)].append(draft)
        monday += timedelta(days=7)


def make_order_tables(drafts, stores_by_id):
    """Give every draft an ID and turn it into orders, lines, returns
    and invoices. Also returns plain facts for the summary tables."""
    orders, lines, returns, invoices = [], [], [], []
    invoiced = []
    gross_by_order = []
    order_id = line_id = return_id = invoice_id = 0

    # Sorting by (day, store) gives order IDs that rise with time.
    for key in sorted(drafts):
        for draft in drafts[key]:
            order_id += 1
            store = stores_by_id[draft.store_id]
            gross = refunds = 0
            for (product_id, quantity, price, discount, returned,
                 delay) in draft.lines:
                line_id += 1
                amount = quantity * price - discount
                gross += amount
                lines.append((line_id, order_id, product_id, quantity,
                              money(price), money(discount),
                              money(amount)))
                if not returned:
                    continue
                return_day = draft.day + timedelta(days=delay)
                # A return after the last day of data hasn't happened.
                if return_day > config.END:
                    continue
                refund = amount * returned // quantity
                refunds += refund
                return_id += 1
                returns.append((return_id, order_id, line_id, return_day,
                                returned, money(refund)))

            # Chapters 1 and 2: orders.revenue is gross at checkout. It
            # keeps cancelled orders and ignores refunds.
            status = "cancelled" if draft.cancelled else "completed"
            channel = "online" if store.is_online else "store"
            orders.append((order_id, draft.day, draft.store_id,
                           draft.customer_id, draft.rep_id, channel,
                           status, money(gross)))
            gross_by_order.append((draft.day, draft.store_id, gross))

            if draft.cancelled:
                continue
            # invoices.revenue is net: after discounts and refunds.
            # That is the number finance reports.
            posted = draft.day + timedelta(days=draft.post_delay)
            if posted > config.INVOICES_LOADED_THROUGH:
                continue
            invoice_id += 1
            net = gross - refunds
            invoices.append((invoice_id, order_id, draft.day, posted,
                             money(net)))
            invoiced.append((draft.day, store, draft.rep_id, net))
    return orders, lines, returns, invoices, invoiced, gross_by_order


# ------------------------------------------------------------------
# Summary tables built from the orders
# ------------------------------------------------------------------


def make_targets(seed, maker, stores, invoiced):
    rng = child_rng(seed, "targets")
    # Plans use the generator's own expected order counts and Kora's
    # average net revenue per order.
    total_net = sum(net for _, _, _, net in invoiced)
    per_order = total_net / maker.total_expected

    plans = {}
    for year, quarter in cal.quarters(config.FIRST_QUARTER,
                                      config.LAST_TARGET_QUARTER):
        first = cal.quarter_start(year, quarter)
        last = cal.quarter_end(year, quarter)
        for store in stores:
            begin = max(first, store.opened_on)
            if begin > last:
                continue
            # Chapter 8: the plan ignores closed_on. The closed East
            # store keeps getting targets, so summing store targets
            # overstates what East was asked to sell.
            orders = sum(maker.expected(store, day)
                         for day in cal.date_range(begin, last))
            stretch = 0.97 + 0.08 * rng.random()
            plans[(year, quarter, store.store_id)] = int(
                orders * per_order * stretch + 0.5
            )

    # Story 2: pin North's FY2027 Q1 total 3% above what it delivered.
    north = [s.store_id for s in stores if s.region == "North"]
    north_net = sum(
        net for day, store, _, net in invoiced
        if store.region == "North" and cal.quarter_of(day) == story.NORTH_Q1
    )
    year, quarter = story.NORTH_Q1
    keys = [(year, quarter, store_id) for store_id in north]
    pinned = story.north_q1_targets(north_net, [plans[k] for k in keys])
    plans.update(zip(keys, pinned))

    return [(target_id, store_id, year, quarter, money(cents))
            for target_id, ((year, quarter, store_id), cents)
            in enumerate(plans.items(), start=1)]


def make_finance_totals(invoiced):
    # Finance closes each quarter on the net invoice total, grouped by
    # invoice date and the store's sales region.
    totals = {}
    for day, store, _, net in invoiced:
        key = (*cal.quarter_of(day), store.region)
        totals[key] = totals.get(key, 0) + net

    rows = []
    for year, quarter in cal.quarters(config.FIRST_QUARTER,
                                      config.LAST_CLOSED_QUARTER):
        closed_on = cal.add_business_days(
            cal.quarter_end(year, quarter), config.CLOSE_BUSINESS_DAYS
        )
        for region in config.REGIONS:
            cents = totals.get((year, quarter, region), 0)
            rows.append((year, quarter, region, money(cents), closed_on))
    return rows


def commission_pay_date(year, month):
    # Chapter 6: monthly commission is paid on the 15th of the month
    # after next. Earned in May, paid on 15 July.
    first = cal.fiscal_month_start(year, month)
    return cal.add_months(first.replace(day=config.COMMISSION_PAY_DAY), 2)


def make_commissions(invoiced):
    earned = {}
    yearly = {}
    for day, _, rep_id, net in invoiced:
        year, month = cal.fiscal_year(day), cal.fiscal_month(day)
        if (year, month) <= config.LAST_COMMISSION_MONTH:
            key = (year, month, rep_id)
            earned[key] = earned.get(key, 0) + net
        yearly[(year, rep_id)] = yearly.get((year, rep_id), 0) + net

    earned_rows = []
    paid = []
    rate = config.COMMISSION_RATE_PCT
    for year, month, rep_id in sorted(earned):
        amount = (earned[(year, month, rep_id)] * rate + 50) // 100
        earned_rows.append((len(earned_rows) + 1, rep_id, year, month,
                            money(amount)))
        pay_day = commission_pay_date(year, month)
        if pay_day <= config.END:
            paid.append((pay_day, rep_id, 0, year, month, amount))

    # Chapter 6: every 15 May, the bonus for the fiscal year that just
    # ended is paid on top. It covers a whole year, so it has no
    # fiscal month. Early in a year, "paid" is mostly last year.
    pay_month, pay_dom = config.BONUS_PAY_MONTH_DAY
    bonus_rate = config.ANNUAL_BONUS_RATE_PCT
    for year, rep_id in sorted(yearly):
        pay_day = date(year, pay_month, pay_dom)
        if pay_day > config.END:
            continue
        amount = (yearly[(year, rep_id)] * bonus_rate + 50) // 100
        paid.append((pay_day, rep_id, 1, year, None, amount))

    paid.sort(key=lambda row: row[:3])
    paid_rows = [(paid_id, rep_id, pay_day, year, month, money(amount))
                 for paid_id, (pay_day, rep_id, _, year, month, amount)
                 in enumerate(paid, start=1)]
    return earned_rows, paid_rows


def make_partner_sales(seed, stores, gross_by_order):
    rng = child_rng(seed, "partner")
    gross = {}
    for day, store_id, cents in gross_by_order:
        if day <= config.PARTNER_PROGRAM_END:
            key = (day.replace(day=1), store_id)
            gross[key] = gross.get(key, 0) + cents

    rows = []
    month = config.START.replace(day=1)
    while month <= config.PARTNER_PROGRAM_END:
        for store in stores:
            cents = gross.get((month, store.store_id), 0)
            # The reseller program only ran through physical stores.
            if store.is_online or not cents:
                continue
            revenue = story.partner_revenue(cents, rng)
            rows.append((len(rows) + 1, store.store_id, month,
                         money(revenue)))
        month = cal.add_months(month, 1)
    return rows


def make_fiscal_calendar():
    return [
        (day, cal.fiscal_year(day), cal.fiscal_quarter(day),
         cal.fiscal_month(day), cal.week_start(day),
         cal.is_quarter_end(day))
        for day in cal.date_range(config.START, config.CALENDAR_END)
    ]


# ------------------------------------------------------------------
# Putting it together
# ------------------------------------------------------------------


def generate_tables(seed=config.SEED):
    """Build every table. Returns {table_name: rows} in load order."""
    stores = make_stores(seed)
    stores_by_id = {store.store_id: store for store in stores}
    north = [store for store in stores if store.region == "North"]
    products = make_products(seed)
    customers, customer_pools, big_customer = make_customers(seed, stores)
    reps, rep_pools = make_reps(seed, stores)

    maker = OrderMaker(seed, stores, products, customer_pools, rep_pools)
    drafts = {}
    for store in stores:
        for day in maker.open_days(store):
            drafts[(day, store.store_id)] = maker.store_day(store, day)

    # The big customer always deals with the store's longest-serving
    # rep, which is how key accounts usually work.
    big_rep = rep_pools[story.BIG_CUSTOMER_STORE_ID][1][0]
    prev, last = apply_north_week_story(drafts, maker, north)
    add_big_customer_orders(drafts, maker, north, big_customer, big_rep,
                            prev, last)

    (orders, order_lines, returns, invoices, invoiced,
     gross_by_order) = make_order_tables(drafts, stores_by_id)
    commission_earned, commission_paid = make_commissions(invoiced)

    tables = {
        "regions": [(n, name) for n, name
                    in enumerate(config.REGIONS, start=1)],
        "warehouses": list(config.WAREHOUSES),
        # is_active is TRUE for every store, including the closed one.
        # Nobody updated it. (Chapters 4 and 8.)
        "stores": [(s.store_id, s.name, s.region, s.warehouse_id, s.city,
                    s.opened_on, s.closed_on, True) for s in stores],
        "products": [(p.product_id, p.sku, p.name, p.category,
                      p.description, money(p.price), money(p.cost))
                     for p in products],
        "customers": customers,
        "sales_reps": reps,
        "orders": orders,
        "order_lines": order_lines,
        "returns": returns,
        "invoices": invoices,
        "partner_sales": make_partner_sales(seed, stores, gross_by_order),
        "fiscal_calendar": make_fiscal_calendar(),
        "targets": make_targets(seed, maker, stores, invoiced),
        "commission_earned": commission_earned,
        "commission_paid": commission_paid,
        "app_users": list(config.APP_USERS),
        "finance_closed_totals": make_finance_totals(invoiced),
    }

    # Chapters 1 and 10: invoices are loaded a few days behind the
    # rest, and this table is the only place that says so.
    tables["data_loads"] = [
        (name, config.INVOICES_LOADED_THROUGH if name == "invoices"
         else config.END)
        for name in tables
    ]
    return tables


# ------------------------------------------------------------------
# Noise tables (chapter 5.4: finding the right table in a big schema)
# ------------------------------------------------------------------

NOISE_TEMPLATES = (
    (("region", "VARCHAR"), ("period_start", "DATE"),
     ("revenue", "DECIMAL(12,2)")),
    (("sku", "VARCHAR"), ("warehouse", "VARCHAR"),
     ("on_hand", "INTEGER")),
    (("campaign_code", "VARCHAR"), ("start_date", "DATE"),
     ("spend", "DECIMAL(12,2)")),
    (("store_code", "VARCHAR"), ("week_start", "DATE"),
     ("revenue", "DECIMAL(12,2)"), ("units", "INTEGER")),
    (("ticket_ref", "VARCHAR"), ("opened_on", "DATE"),
     ("status", "VARCHAR")),
    (("supplier_code", "VARCHAR"), ("invoice_month", "DATE"),
     ("amount", "DECIMAL(12,2)")),
)

NOISE_WORDS = {
    "region": config.SALES_REGIONS,
    "warehouse": tuple(name for _, name, _ in config.WAREHOUSES),
    "status": ("open", "closed", "pending"),
}


def noise_value(rng, column, sql_type, row):
    if sql_type == "DATE":
        return random_day(rng, config.START, config.END)
    if sql_type == "INTEGER":
        return rng.randint(0, 500)
    if sql_type.startswith("DECIMAL"):
        return money(rng.randint(1_000, 5_000_000))
    if column in NOISE_WORDS:
        return rng.choice(NOISE_WORDS[column])
    prefix = column.split("_")[0][:3].upper()
    return f"{prefix}-{rng.randint(1, 9999):04d}"


def noise_tables(seed, count):
    """Extra tables that look plausible and mean nothing.

    Returns a list of (name, columns, rows).
    """
    tables = []
    for n in range(1, count + 1):
        rng = child_rng(seed, "noise", n)
        columns = (("id", "INTEGER"),) + NOISE_TEMPLATES[
            (n - 1) % len(NOISE_TEMPLATES)
        ]
        rows = [
            (row,) + tuple(noise_value(rng, col, sql_type, row)
                           for col, sql_type in columns[1:])
            for row in range(1, rng.randint(50, 300) + 1)
        ]
        tables.append((f"noise_{n:04d}", columns, rows))
    return tables
