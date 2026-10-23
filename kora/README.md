# Kora data dictionary

Kora is a fictional mid-size retailer with stores in four sales
regions and an online shop. This folder holds the script that builds
Kora's database with a fixed random seed, so every reader gets exactly
the same numbers and the answers in the book always match. It is built
in chapter 1 and explained in appendix A.

Build it from the repo root:

```bash
python scripts/setup_kora.py
```

All tables live in DuckDB's default schema (`main`). Amounts are in
USD. Data runs from 2023-05-01 to 2026-08-09.

## Fiscal calendar

Kora's fiscal year starts on 1 May and is named after the calendar
year it ends in, so FY2024 runs from 2023-05-01 to 2024-04-30. Q1 is
May to July, Q2 is August to October, Q3 is November to January and
Q4 is February to April. Fiscal weeks run Monday to Sunday.

## Tables

### regions
Kora's regions.
- `region_id`: region key.
- `region_name`: North, South, East, West or Online.

### warehouses
Distribution centers that ship stock to stores.
- `warehouse_id`: warehouse key.
- `warehouse_name`: the warehouse's name.
- `region`: the supply chain group the warehouse belongs to.

### stores
Every Kora store, plus the online shop.
- `store_id`: store key.
- `store_name`: the store's trading name.
- `region`: the sales region the store reports to.
- `warehouse_id`: the warehouse that supplies the store.
- `city`: the town the store is in. Empty for the online shop.
- `opened_on`: the date the store opened.
- `closed_on`: the date the store closed, if it has.
- `is_active`: the store's active flag in the store master.

### products
The product catalog.
- `product_id`: product key.
- `sku`: stock keeping unit code.
- `product_name`: the name shown on the shelf and the website.
- `category`: product category.
- `description`: the product description from the website.
- `unit_price`: current list price.
- `unit_cost`: what Kora pays the supplier for one unit.

### customers
Customer accounts. No personal details are kept here.
- `customer_id`: customer key.
- `customer_type`: `retail` or `business`.
- `home_store_id`: the store the customer signed up at.
- `created_on`: the date the account was created.

### sales_reps
Sales staff, by code.
- `rep_id`: rep key.
- `rep_code`: the rep's staff code.
- `store_id`: the store the rep works at.
- `region`: the rep's sales region.
- `hired_on`: the rep's start date.

### orders
One row per order at checkout.
- `order_id`: order key.
- `order_date`: the date the order was placed.
- `store_id`: the store that took the order.
- `customer_id`: the customer who placed it.
- `rep_id`: the rep credited with the sale.
- `channel`: `store` or `online`.
- `status`: `completed` or `cancelled`.
- `revenue`: order value at checkout.

### order_lines
One row per product on an order.
- `order_line_id`: order line key.
- `order_id`: the order the line belongs to.
- `product_id`: the product sold.
- `quantity`: units sold.
- `unit_price`: price per unit at the time of sale.
- `discount_amount`: discount taken off the line.
- `line_amount`: quantity times unit price, less the discount.

### returns
Products customers brought back.
- `return_id`: return key.
- `order_id`: the original order.
- `order_line_id`: the order line being returned.
- `return_date`: the date the return was processed.
- `quantity`: units returned.
- `refund_amount`: money given back to the customer.

### invoices
Finance's invoice records.
- `invoice_id`: invoice key.
- `order_id`: the order the invoice is for.
- `invoice_date`: the invoice date.
- `posted_date`: the date the invoice was posted to the ledger.
- `revenue`: invoiced revenue.

### partner_sales
Monthly figures from Kora's reseller program.
- `partner_sale_id`: row key.
- `store_id`: the store the partner sales are booked to.
- `sale_month`: the first day of the month.
- `revenue`: the partner's reported revenue for the month.

### fiscal_calendar
One row per day, with Kora's fiscal labels.
- `calendar_date`: the date.
- `fiscal_year`: fiscal year, for example 2027.
- `fiscal_quarter`: 1 to 4.
- `fiscal_month`: 1 to 12, where 1 is May.
- `fiscal_week_start`: the Monday that starts the date's week.
- `is_quarter_end`: true on the last day of a fiscal quarter.

### targets
Quarterly revenue targets from the annual plan.
- `target_id`: target key.
- `store_id`: the store the target is for.
- `fiscal_year`: fiscal year.
- `fiscal_quarter`: fiscal quarter.
- `target_revenue`: the net revenue the store is expected to make.

### commission_earned
Commission earned by each rep each month.
- `earned_id`: row key.
- `rep_id`: the rep.
- `fiscal_year`: fiscal year the commission was earned in.
- `fiscal_month`: fiscal month the commission was earned in.
- `earned_amount`: commission earned.

### commission_paid
Commission payments made through payroll.
- `paid_id`: row key.
- `rep_id`: the rep.
- `paid_date`: the payroll date.
- `fiscal_year`: fiscal year the payment covers.
- `fiscal_month`: fiscal month the payment covers. Empty for the
  annual bonus, which covers a whole year.
- `paid_amount`: amount paid.

### app_users
People who use Kora's data agent.
- `user_id`: user key.
- `display_name`: the user's first name.
- `role`: `regional_manager`, `finance` or `analyst`.
- `region_scope`: the sales region the user may see, or `ALL`.

### finance_closed_totals
Finance's signed-off net revenue for each closed quarter.
- `fiscal_year`: fiscal year.
- `fiscal_quarter`: fiscal quarter.
- `region`: sales region.
- `net_revenue`: the closed net revenue figure.
- `closed_on`: the date finance closed the quarter.

### data_loads
When each table was last loaded.
- `table_name`: the table.
- `loaded_through`: the last date of data in the table.

## How the tables connect

Foreign keys are declared on the ID columns (for example
`orders.store_id` to `stores.store_id`). The `region` columns hold
names, not IDs, so they have no foreign key:

- `stores.region` and `sales_reps.region` hold a
  `regions.region_name`.
- `warehouses.region` holds a supply chain group name.
- `finance_closed_totals.region` holds a `regions.region_name`.
- `targets` and `commission_*` use fiscal year, quarter and month
  numbers that match `fiscal_calendar`.
- `data_loads.table_name` holds a table name in this schema.
