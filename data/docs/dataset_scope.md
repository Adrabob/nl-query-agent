# Dataset Scope & Limitations  -  Online Retail Dataset

This document describes exactly what the Online Retail dataset covers, what
questions it can and cannot answer, and how to interpret results correctly.
It is the authoritative reference for understanding the boundaries of the
NL Query Agent's structured-data layer.

---

## What the Dataset Is

**Source:** UCI Machine Learning Repository / Kaggle "Online Retail" dataset.
**Publisher:** A UK-based online retailer (anonymised).
**License:** Open-source / public domain  -  no restrictions on use.
**Time range:** 1 December 2010 - 9 December 2011 (approximately 12 months).

The retailer sells gift and homeware products, primarily to **wholesale / trade
customers** (businesses, resellers) rather than individual consumers. This
explains the bulk quantities seen on many invoices.

---

## Schema Summary

The data has been normalised into four relational tables:

| Table | Key Columns | Row Count (approx.) |
|-------|-------------|---------------------|
| `customers` | `customer_id`, `country` | 4,372 |
| `products` | `stock_code`, `description` | 4,070 |
| `invoices` | `invoice_no`, `invoice_date`, `customer_id` | 25,900 |
| `invoice_lines` | `invoice_no`, `stock_code`, `quantity`, `unit_price` | 541,909 |

Revenue = `quantity * unit_price` (no separate revenue column exists; it is
always a derived calculation). All monetary values are in **GBP**.

---

## What This Dataset CAN Answer

- **Revenue questions:** total revenue, revenue by country, revenue by product,
  revenue by time period (monthly / quarterly), top N customers or products by
  revenue.
- **Volume questions:** total units sold, bestselling products by quantity,
  most active customers by order count.
- **Growth questions:** month-over-month revenue growth by country or product
  (using the formula: `[Revenue(t) - Revenue(t-1)] / Revenue(t-1)`). Note:
  only month-over-month is valid  -  the dataset does not span multiple years.
- **Revenue share:** proportion of total revenue attributable to each country
  or product (`Revenue(entity) / Total Revenue`).
- **Product ranking:** ranking products by units sold in a given month or quarter.
- **Return / cancellation analysis:** return rate by product or country, total
  value of returned goods, customers with the most cancellations.
- **Return rate by product:** `ReturnedUnits(product) / SoldUnits(product)`.
- **Customer questions:** number of unique customers, customers by country,
  top customers by spend, active customers in a period, repeat customer rate.
- **Repeat purchase rate by product:** proportion of customers who bought a
  specific product more than once.
- **Product questions:** most/least popular products, products never returned,
  products with the highest or lowest unit prices.
- **Time-series questions:** monthly revenue trends, quarterly order volumes,
  seasonal patterns (within the ~12-month window).
- **Geographic questions:** revenue or volume breakdown by country, UK vs
  international split, revenue share by country.

---

## What This Dataset CANNOT Answer

The following questions **cannot be answered** from the source data. Asking them
will return an error or a disclaimer, not a fabricated number.

### 1. Gross Margin / Profit / Cost of Goods Sold (COGS)
**There is no cost column in the dataset.** This is the most important
limitation for financial analysis. `UnitPrice` is the selling price only.
Without cost data, gross margin, net margin, and profitability by product or
customer cannot be calculated. Any "margin" figure would require a synthetic
assumption and should be clearly labelled as estimated, not actual.

> This limitation should be flagged proactively whenever a user asks about
> profit, margin, or EBITDA  -  not only when explicitly asked.

### 2. Year-Over-Year Growth
The data covers approximately one calendar year. There is no prior-year period
to compare against. Month-on-month growth is valid and meaningful; year-over-year
is not possible with this dataset.

### 3. Individual Consumer Demographics
The dataset has no age, gender, or demographic information. Customer segmentation
is limited to geography (`country`) and purchase behaviour (spend, frequency,
product mix).

### 4. Inventory / Stock Levels
The data records what was sold, not what is in stock. Questions about current
inventory, stock-outs, or reorder points cannot be answered.

### 5. Shipping / Delivery Data
There are no shipping dates, delivery times, or logistics fields. Lead-time or
fulfilment questions cannot be answered.

### 6. Product Categories
The source data has no category or product-family hierarchy  -  only free-text
`Description` and `StockCode`. Category-level analysis requires grouping by
description keywords (approximate) or a manually created mapping, which is not
part of the base dataset.

### 7. Pricing History / Discounts
The dataset records the price at transaction time only. It does not record list
prices, promotional prices, or discount amounts.

---

## Data Quality Notes

### NULL CustomerID
Approximately **24% of transaction rows** (approximately 133,000 rows) have a
NULL `CustomerID`. These are valid sales  -  the transaction happened and the
revenue is real  -  but they cannot be attributed to a specific customer. They are:
- **Included** in aggregate revenue and volume figures.
- **Excluded** from all per-customer analyses (top customers by spend, repeat
  purchase rate, customer lifetime value, retention).

### Negative Quantities
Negative `Quantity` values indicate returns or cancellations. A quantity of `-6`
means 6 units were returned. These rows are always paired with a cancellation
invoice (InvoiceNo starting with 'C') in this dataset.

### December 2010 Partial Data
The earliest data is 1 December 2010. December 2010 represents only the first
month of the dataset and should not be treated as a full trading month.

### December 2011 Partial Data
The dataset ends on 9 December 2011. Any December 2011 figures represent fewer
than 10 days of trading and will appear artificially low compared with earlier
complete months.

---

## Geographic Coverage

The dataset includes transactions from approximately **37 countries**.
The United Kingdom accounts for approximately **84% of total revenue**.
The remaining 16% is spread across international wholesale customers.

Top countries by revenue contribution (approximate):
1. United Kingdom (~84%)
2. Netherlands
3. EIRE (Ireland)
4. Germany
5. France
6. Australia
7. Switzerland
8. Spain
9. Belgium
10. Sweden

---

## Interpreting "Revenue" in Results

Unless otherwise stated, revenue in query results means **net revenue**:

```
SUM(quantity * unit_price)
WHERE quantity > 0 AND invoice_no NOT LIKE 'C%'
```

Currency is **GBP** throughout. If a result includes cancellation rows
(negative quantities), that will be noted explicitly.
