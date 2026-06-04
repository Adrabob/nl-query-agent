# Golden Question Set — Online Retail NL Query Agent

Each entry: **Question** → **Expected SQL** → **Expected result / row count**

Finance team: please review each question. For every one, confirm:
- Does a real analyst at this company actually ask this? ✅ / ❌
- Is the expected result sensible given the dataset? ✅ / ❌ / 🤔 (unsure)
- Add any extra questions you'd ask at the bottom of each tier.

---

## Tier 1 — Simple (single-table lookup or filter)

### Q1 — How many customers do we have?
```sql
SELECT COUNT(DISTINCT customer_id) AS customer_count FROM customers;
```
**Expected:** 1 row — `4372`

---

### Q2 — How many products do we sell?
```sql
SELECT COUNT(*) AS product_count FROM products;
```
**Expected:** 1 row — `4070`

---

### Q3 — Show all customers from Germany.
```sql
SELECT customer_id, country FROM customers WHERE country = 'Germany';
```
**Expected:** ~95 rows, all `country = 'Germany'`

---

### Q4 — How many invoices do we have in total?
```sql
SELECT COUNT(*) AS invoice_count FROM invoices;
```
**Expected:** 1 row — `25900`

---

### Q5 — What is the unit price of product stock code 85123A?
```sql
SELECT il.unit_price
FROM invoice_lines il
WHERE il.stock_code = '85123A'
FETCH FIRST 1 ROW ONLY;
```
**Expected:** 1 row — a price around £2.55

---

## Tier 2 — Medium (aggregation, grouping, ranking)

### Q6 — What is total net revenue by country? (top 10)
```sql
SELECT c.country,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS net_revenue
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN customers c ON i.customer_id = c.customer_id
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
GROUP BY c.country
ORDER BY net_revenue DESC
FETCH FIRST 10 ROWS ONLY;
```
**Expected:** 10 rows, United Kingdom first with ~£6.7M

---

### Q7 — What are the top 10 best-selling products by revenue?
```sql
SELECT p.stock_code,
       p.description,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS revenue
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN products p  ON il.stock_code = p.stock_code
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
GROUP BY p.stock_code, p.description
ORDER BY revenue DESC
FETCH FIRST 10 ROWS ONLY;
```
**Expected:** 10 rows, decorative/gift items dominating

---

### Q8 — What is the total revenue per month in 2011?
```sql
SELECT TRUNC(i.invoice_date, 'MM') AS month,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS net_revenue
FROM invoice_lines il
JOIN invoices i ON il.invoice_no = i.invoice_no
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
  AND EXTRACT(YEAR FROM i.invoice_date) = 2011
GROUP BY TRUNC(i.invoice_date, 'MM')
ORDER BY month;
```
**Expected:** 11 rows (Jan–Nov 2011; Dec 2011 is only 9 days so very low)

---

### Q9 — Which country has the highest average order value?
```sql
SELECT c.country,
       ROUND(SUM(il.quantity * il.unit_price) /
             COUNT(DISTINCT i.invoice_no), 2) AS avg_order_value
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN customers c ON i.customer_id = c.customer_id
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
GROUP BY c.country
HAVING COUNT(DISTINCT i.invoice_no) >= 10
ORDER BY avg_order_value DESC
FETCH FIRST 5 ROWS ONLY;
```
**Expected:** 5 rows — Netherlands and Singapore tend to have high AOV

---

### Q10 — How many orders were cancelled, and what is their total value?
```sql
SELECT COUNT(DISTINCT i.invoice_no)               AS cancelled_invoices,
       ROUND(SUM(ABS(il.quantity * il.unit_price)), 2) AS total_return_value
FROM invoices i
JOIN invoice_lines il ON i.invoice_no = il.invoice_no
WHERE i.invoice_no LIKE 'C%';
```
**Expected:** 1 row — ~2,215 invoices, ~£838K

---

### Q11 — What percentage of our invoices are cancellations?
```sql
SELECT ROUND(
    100.0 * SUM(CASE WHEN invoice_no LIKE 'C%' THEN 1 ELSE 0 END)
          / COUNT(*), 2
) AS cancellation_rate_pct
FROM invoices;
```
**Expected:** 1 row — around 8–9%

---

### Q12 — What are the top 5 products with the most returns (by units)?
```sql
SELECT p.stock_code,
       p.description,
       SUM(ABS(il.quantity)) AS units_returned
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN products p  ON il.stock_code = p.stock_code
WHERE il.quantity < 0
   OR i.invoice_no LIKE 'C%'
GROUP BY p.stock_code, p.description
ORDER BY units_returned DESC
FETCH FIRST 5 ROWS ONLY;
```
**Expected:** 5 rows of high-volume products with return issues

---

## Tier 3 — Complex (multi-table joins, multi-turn, RAG)

### Q13 — Who are the top 5 customers by total spend, and where are they from?
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
FETCH FIRST 5 ROWS ONLY;
```
**Expected:** 5 rows — highest spender typically ~£280K, often Netherlands

---

### Q14 — For the top 3 customers by spend, what were their top 3 purchased products?
*(Multi-step — demo shows multi-turn: first ask Q13, then ask this as a follow-up)*
```sql
WITH top_customers AS (
    SELECT i.customer_id
    FROM invoice_lines il JOIN invoices i ON il.invoice_no = i.invoice_no
    WHERE il.quantity > 0 AND i.invoice_no NOT LIKE 'C%' AND i.customer_id IS NOT NULL
    GROUP BY i.customer_id
    ORDER BY SUM(il.quantity * il.unit_price) DESC
    FETCH FIRST 3 ROWS ONLY
)
SELECT i.customer_id,
       p.description,
       SUM(il.quantity) AS units_bought
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN products p  ON il.stock_code = p.stock_code
WHERE i.customer_id IN (SELECT customer_id FROM top_customers)
  AND il.quantity > 0
GROUP BY i.customer_id, p.description
ORDER BY i.customer_id, units_bought DESC;
```
**Expected:** multiple rows, top products per high-value customer

---

### Q15 — What is the monthly revenue trend for UK customers in 2011?
```sql
SELECT TRUNC(i.invoice_date, 'MM') AS month,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS uk_revenue
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN customers c ON i.customer_id = c.customer_id
WHERE c.country = 'United Kingdom'
  AND il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
  AND EXTRACT(YEAR FROM i.invoice_date) = 2011
GROUP BY TRUNC(i.invoice_date, 'MM')
ORDER BY month;
```
**Expected:** 11 rows, November 2011 typically the peak month (pre-Christmas)

---

### Q16 — Multi-turn sequence (scripted for demo)

**Turn 1:** "Show total revenue by country for 2011"
*(system returns table with all countries)*

**Turn 2:** "Now only show countries with revenue above £50,000"
*(system uses session context — no need to repeat "by country for 2011")*

**Expected SQL for turn 2:**
```sql
-- Select AI should resolve the follow-up with context from turn 1
SELECT c.country,
       ROUND(SUM(il.quantity * il.unit_price), 2) AS net_revenue
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN customers c ON i.customer_id = c.customer_id
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
  AND EXTRACT(YEAR FROM i.invoice_date) = 2011
GROUP BY c.country
HAVING SUM(il.quantity * il.unit_price) > 50000
ORDER BY net_revenue DESC;
```
**Expected:** ~5–7 countries

---

### Q17 — Which countries are growing their purchases month over month?
```sql
WITH monthly AS (
    SELECT c.country,
           TRUNC(i.invoice_date, 'MM') AS month,
           SUM(il.quantity * il.unit_price) AS revenue
    FROM invoice_lines il
    JOIN invoices i  ON il.invoice_no = i.invoice_no
    JOIN customers c ON i.customer_id = c.customer_id
    WHERE il.quantity > 0 AND i.invoice_no NOT LIKE 'C%'
    GROUP BY c.country, TRUNC(i.invoice_date, 'MM')
)
SELECT country, month,
       ROUND(revenue, 2) AS revenue,
       ROUND(
           100.0 * (revenue - LAG(revenue) OVER (PARTITION BY country ORDER BY month))
               / NULLIF(LAG(revenue) OVER (PARTITION BY country ORDER BY month), 0),
           2
       ) AS mom_growth_pct
FROM monthly
ORDER BY country, month
```
**Expected:** multi-row table; UK and top 5 countries show seasonal growth pattern

---

### Q18 — What is each country's share of total revenue?
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
WHERE il.quantity > 0 AND i.invoice_no NOT LIKE 'C%'
GROUP BY c.country
ORDER BY net_revenue DESC
```
**Expected:** UK ~84%, then Netherlands, EIRE, Germany, France in single digits

---

### Q19 — What are the top 10 products by units sold in November 2011?
*(Product Growth Ranking — demo month chosen as November, the peak trading month)*
```sql
SELECT p.stock_code,
       p.description,
       SUM(il.quantity) AS units_sold,
       RANK() OVER (ORDER BY SUM(il.quantity) DESC) AS rank
FROM invoice_lines il
JOIN invoices i  ON il.invoice_no = i.invoice_no
JOIN products p  ON il.stock_code = p.stock_code
WHERE il.quantity > 0
  AND i.invoice_no NOT LIKE 'C%'
  AND TRUNC(i.invoice_date, 'MM') = DATE '2011-11-01'
GROUP BY p.stock_code, p.description
ORDER BY units_sold DESC
FETCH FIRST 10 ROWS ONLY
```
**Expected:** 10 rows; seasonal/gift products dominate

---

### Q20 — Which products have the highest return rate?
```sql
WITH sold AS (
    SELECT il.stock_code, SUM(il.quantity) AS units_sold
    FROM invoice_lines il JOIN invoices i ON il.invoice_no = i.invoice_no
    WHERE il.quantity > 0 AND i.invoice_no NOT LIKE 'C%'
    GROUP BY il.stock_code
),
returned AS (
    SELECT il.stock_code, SUM(ABS(il.quantity)) AS units_returned
    FROM invoice_lines il JOIN invoices i ON il.invoice_no = i.invoice_no
    WHERE il.quantity < 0 OR i.invoice_no LIKE 'C%'
    GROUP BY il.stock_code
)
SELECT p.stock_code, p.description,
       s.units_sold, COALESCE(r.units_returned, 0) AS units_returned,
       ROUND(100.0 * COALESCE(r.units_returned, 0) / NULLIF(s.units_sold, 0), 2) AS return_rate_pct
FROM products p
JOIN sold s     ON p.stock_code = s.stock_code
LEFT JOIN returned r ON p.stock_code = r.stock_code
WHERE s.units_sold >= 10
ORDER BY return_rate_pct DESC
FETCH FIRST 10 ROWS ONLY
```
**Expected:** 10 rows; high-return products flagged for investigation

---

### Q21 — Which products do customers come back to buy again?
*(Repeat Purchase Rate by Product)*
```sql
WITH per_customer AS (
    SELECT il.stock_code, i.customer_id,
           COUNT(DISTINCT i.invoice_no) AS times_purchased
    FROM invoice_lines il JOIN invoices i ON il.invoice_no = i.invoice_no
    WHERE il.quantity > 0 AND i.invoice_no NOT LIKE 'C%' AND i.customer_id IS NOT NULL
    GROUP BY il.stock_code, i.customer_id
)
SELECT p.stock_code, p.description,
       COUNT(*) AS total_customers,
       SUM(CASE WHEN times_purchased > 1 THEN 1 ELSE 0 END) AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN times_purchased > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_rate_pct
FROM per_customer pc JOIN products p ON pc.stock_code = p.stock_code
GROUP BY p.stock_code, p.description
HAVING COUNT(*) >= 10
ORDER BY repeat_rate_pct DESC
FETCH FIRST 10 ROWS ONLY
```
**Expected:** 10 rows; consumable products (gift wrap, cake cases) likely top this list

---

### Q22 — RAG: What counts as a return in this dataset?
*(routes to /ask_docs — answered from business_glossary.md, not SQL)*

**Expected answer:** explanation that returns are identified by InvoiceNo starting with 'C' and/or Quantity < 0; no separate returns column exists.
**Expected sources:** `[business_glossary.md]`

---

### Q23 — RAG: Can we calculate gross margin from this data?
*(routes to /ask_docs — answered from dataset_scope.md)*

**Expected answer:** No — there is no cost / COGS column in the dataset. Only selling price (UnitPrice) is available.
**Expected sources:** `[dataset_scope.md]`

---

### Q24 — RAG: How is Average Order Value defined and calculated?
*(routes to /ask_docs — answered from kpi_guide.md)*

**Expected answer:** AOV = total net revenue ÷ number of distinct non-cancelled invoices, with the exact SQL formula.
**Expected sources:** `[kpi_guide.md]`

---

## Finance Team — Your Turn

> Please answer these questions about the list above:
> 1. Which questions above would a real analyst at this company **definitely** ask? (mark ✅)
> 2. Which feel unnatural or wrong for this business? (mark ❌ with a note why)
> 3. What questions are **missing** that you'd expect to see? Add them below.

### Finance team additions:

*(add here)*
