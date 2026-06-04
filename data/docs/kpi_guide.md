# KPI Guide  -  Standard Metric Formulas

This guide defines the standard business KPIs used with the Online Retail dataset
and provides the exact SQL logic for each one. These formulas are the canonical
definitions  -  any query result for these metrics should match this logic.

All formulas reference the normalised schema:
`customers`, `products`, `invoices`, `invoice_lines`.
All monetary values are in **GBP**.

---

## Revenue Metrics

### Net Revenue
Total sales value excluding cancellations and returns.

```sql
SELECT SUM(il.quantity * il.unit_price) AS net_revenue
FROM invoice_lines il
JOIN invoices i ON il.invoice_no = i.invoice_no
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
```

**Use this as the default revenue figure** unless explicitly asked for gross revenue.

### Gross Revenue (includes returns)
```sql
SELECT SUM(il.quantity * il.unit_price) AS gross_revenue
FROM invoice_lines il
```

Because cancelled lines have negative quantity, the sum naturally offsets them.

### Revenue by Country
```sql
SELECT c.country,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS net_revenue
FROM invoice_lines il
JOIN invoices i   ON il.invoice_no = i.invoice_no
JOIN customers c  ON i.customer_id = c.customer_id
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
GROUP BY c.country
ORDER BY net_revenue DESC
```

### Revenue Share by Country
Proportion of total revenue contributed by each country.

```sql
SELECT c.country,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS net_revenue,
       ROUND(
           100.0 * SUM(il.quantity * il.unit_price)
               / SUM(SUM(il.quantity * il.unit_price)) OVER (),
           2
       ) AS revenue_share_pct
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN customers c ON i.customer_id = c.customer_id
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
GROUP BY c.country
ORDER BY net_revenue DESC
```

### Revenue by Month
```sql
SELECT TRUNC(i.invoice_date, 'MM') AS month,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS net_revenue
FROM invoice_lines il
JOIN invoices i ON il.invoice_no = i.invoice_no
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
GROUP BY TRUNC(i.invoice_date, 'MM')
ORDER BY month
```

### Month-over-Month Sales Growth by Country
Which countries are expanding their purchases. Only month-over-month is valid
for this dataset  -  there is insufficient data for year-over-year growth.

```sql
WITH monthly AS (
    SELECT c.country,
           TRUNC(i.invoice_date, 'MM') AS month,
           SUM(il.quantity * il.unit_price) AS revenue
    FROM invoice_lines il
    JOIN invoices i  ON il.invoice_no = i.invoice_no
    JOIN customers c ON i.customer_id = c.customer_id
    WHERE il.quantity > 0
      AND i.invoice_no NOT LIKE 'C%'
    GROUP BY c.country, TRUNC(i.invoice_date, 'MM')
)
SELECT country,
       month,
       ROUND(revenue, 2) AS revenue,
       ROUND(
           100.0 * (revenue - LAG(revenue) OVER (PARTITION BY country ORDER BY month))
               / NULLIF(LAG(revenue) OVER (PARTITION BY country ORDER BY month), 0),
           2
       ) AS mom_growth_pct
FROM monthly
ORDER BY country, month
```

> Formula: `Sales Growth(c, t) = [Revenue(c, t) − Revenue(c, t−1)] / Revenue(c, t−1)`

---

## Customer Metrics

### Total Unique Customers
```sql
SELECT COUNT(DISTINCT i.customer_id) AS unique_customers
FROM invoices i
JOIN invoice_lines il ON i.invoice_no = il.invoice_no
WHERE i.customer_id IS NOT NULL
  AND i.invoice_no NOT LIKE 'C%'
  AND il.quantity > 0
```

### Top Customers by Spend
```sql
SELECT c.customer_id,
       c.country,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS total_spend,
       COUNT(DISTINCT i.invoice_no)               AS order_count
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN customers c ON i.customer_id = c.customer_id
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
  AND i.customer_id IS NOT NULL
GROUP BY c.customer_id, c.country
ORDER BY total_spend DESC
FETCH FIRST 10 ROWS ONLY
```

### Average Order Value (AOV)
```sql
SELECT ROUND(
    SUM(il.quantity * il.unit_price) / COUNT(DISTINCT i.invoice_no),
    2
) AS aov
FROM invoice_lines il
JOIN invoices i ON il.invoice_no = i.invoice_no
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
```

> Formula: `AOV = Net Revenue / COUNT(DISTINCT non-cancelled invoices)`

### Repeat Customer Rate
Percentage of customers who placed more than one order.

```sql
WITH order_counts AS (
    SELECT i.customer_id,
           COUNT(DISTINCT i.invoice_no) AS orders
    FROM invoices i
    JOIN invoice_lines il ON i.invoice_no = il.invoice_no
    WHERE i.customer_id IS NOT NULL
      AND i.invoice_no NOT LIKE 'C%'
      AND il.quantity > 0
    GROUP BY i.customer_id
)
SELECT ROUND(
    100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END) / COUNT(*),
    2
) AS repeat_customer_pct
FROM order_counts
```

---

## Product Metrics

### Top Products by Revenue
```sql
SELECT p.stock_code,
       p.description,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS net_revenue,
       SUM(il.quantity)                            AS units_sold
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN products p  ON il.stock_code = p.stock_code
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
GROUP BY p.stock_code, p.description
ORDER BY net_revenue DESC
FETCH FIRST 10 ROWS ONLY
```

### Product Growth Ranking (Monthly)
Rank products by units sold each month  -  identifies which products are growing.

```sql
WITH monthly_sales AS (
    SELECT il.stock_code,
           p.description,
           TRUNC(i.invoice_date, 'MM') AS month,
           SUM(il.quantity)             AS units_sold
    FROM invoice_lines il
    JOIN invoices i  ON il.invoice_no = i.invoice_no
    JOIN products p  ON il.stock_code = p.stock_code
    WHERE il.quantity > 0
      AND i.invoice_no NOT LIKE 'C%'
    GROUP BY il.stock_code, p.description, TRUNC(i.invoice_date, 'MM')
)
SELECT stock_code,
       description,
       month,
       units_sold,
       RANK() OVER (PARTITION BY month ORDER BY units_sold DESC) AS rank_in_month
FROM monthly_sales
ORDER BY month, rank_in_month
```

> Formula: `UnitsSold(i) = SUM(Quantity)` per product per period, then ranked.

### Repeat Purchase Rate by Product
Proportion of customers who bought a specific product more than once.

```sql
WITH per_customer AS (
    SELECT il.stock_code,
           i.customer_id,
           COUNT(DISTINCT i.invoice_no) AS times_purchased
    FROM invoice_lines il
    JOIN invoices i ON il.invoice_no = i.invoice_no
    WHERE il.quantity > 0
      AND i.invoice_no NOT LIKE 'C%'
      AND i.customer_id IS NOT NULL
    GROUP BY il.stock_code, i.customer_id
)
SELECT pc.stock_code,
       p.description,
       COUNT(*)                                                     AS total_customers,
       SUM(CASE WHEN times_purchased > 1 THEN 1 ELSE 0 END)        AS repeat_customers,
       ROUND(
           100.0 * SUM(CASE WHEN times_purchased > 1 THEN 1 ELSE 0 END)
               / COUNT(*),
           2
       ) AS repeat_purchase_rate_pct
FROM per_customer pc
JOIN products p ON pc.stock_code = p.stock_code
GROUP BY pc.stock_code, p.description
HAVING COUNT(*) >= 5
ORDER BY repeat_purchase_rate_pct DESC
FETCH FIRST 20 ROWS ONLY
```

> Formula: `RepeatPurchaseRate(i) = Customers who bought i ≥2 times / Customers who bought i ≥1 time`

---

## Return & Cancellation Metrics

### Return Rate by Invoice Count
```sql
SELECT ROUND(
    100.0 * SUM(CASE WHEN invoice_no LIKE 'C%' THEN 1 ELSE 0 END)
          / COUNT(*),
    2
) AS cancellation_rate_pct
FROM invoices
```

### Return Rate by Value
More meaningful financially than by invoice count.

```sql
WITH gross AS (SELECT SUM(il.quantity * il.unit_price) AS total FROM invoice_lines il),
     returned AS (
         SELECT SUM(ABS(il.quantity * il.unit_price)) AS total
         FROM invoice_lines il
         JOIN invoices i ON il.invoice_no = i.invoice_no
         WHERE i.invoice_no LIKE 'C%' OR il.quantity < 0
     )
SELECT ROUND(100.0 * returned.total / NULLIF(gross.total, 0), 2) AS return_rate_by_value_pct
FROM gross, returned
```

### Return Rate by Product
Which products are returned most often.

```sql
WITH sold AS (
    SELECT il.stock_code, SUM(il.quantity) AS units_sold
    FROM invoice_lines il
    JOIN invoices i ON il.invoice_no = i.invoice_no
    WHERE il.quantity > 0 AND i.invoice_no NOT LIKE 'C%'
    GROUP BY il.stock_code
),
returned AS (
    SELECT il.stock_code, SUM(ABS(il.quantity)) AS units_returned
    FROM invoice_lines il
    JOIN invoices i ON il.invoice_no = i.invoice_no
    WHERE il.quantity < 0 OR i.invoice_no LIKE 'C%'
    GROUP BY il.stock_code
)
SELECT p.stock_code,
       p.description,
       COALESCE(s.units_sold, 0)     AS units_sold,
       COALESCE(r.units_returned, 0) AS units_returned,
       ROUND(
           100.0 * COALESCE(r.units_returned, 0)
               / NULLIF(COALESCE(s.units_sold, 0), 0),
           2
       ) AS return_rate_pct
FROM products p
LEFT JOIN sold s     ON p.stock_code = s.stock_code
LEFT JOIN returned r ON p.stock_code = r.stock_code
WHERE COALESCE(s.units_sold, 0) > 0
ORDER BY return_rate_pct DESC
FETCH FIRST 20 ROWS ONLY
```

> Formula: `ReturnRate(i) = ReturnedUnits(i) / SoldUnits(i)`

---

## Caveats

- **No COGS / margin metric is defined here.** There is no cost data in the dataset.
  This is the most important limitation for financial analysis.
- **Year-over-year growth is not computable.** The data spans ~12 months only.
  Use month-over-month growth instead.
- **NULL CustomerID rows are excluded** from all per-customer KPIs. They are
  included in aggregate revenue and volume totals.
- **December 2010 and December 2011 are partial months.** Treat them with caution
  in trend analysis.
- **All monetary values are in GBP.** No currency conversion is available.
