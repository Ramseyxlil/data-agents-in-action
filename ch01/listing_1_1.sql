-- Listing 1.1: the wrong query from section 1.2, on purpose.
-- It sums gross order revenue for calendar April to June. Finance
-- means net invoiced revenue for fiscal Q1 (May to July).
SELECT SUM(o.revenue)
FROM orders o
JOIN stores s ON o.store_id = s.store_id
WHERE s.region = 'North'
  AND o.order_date >= '2026-04-01'
  AND o.order_date <  '2026-07-01';
