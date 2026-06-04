# Business Glossary  -  Online Retail Dataset

This glossary defines the key terms and concepts as they apply specifically to
the Online Retail dataset (UCI / Kaggle, Dec 2010 - Dec 2011). Use these
definitions when interpreting query results or business questions about this data.

---

## Core Entities

### Invoice
A single sales transaction. Each invoice is identified by a unique `InvoiceNo`
and records the date, the customer (if known), and one or more line items.

- Normal invoices have a numeric `InvoiceNo` (e.g. `536365`).
- Cancelled invoices have an `InvoiceNo` beginning with the letter **C**
  (e.g. `C536379`). These represent order cancellations or returns.
- One invoice can contain multiple products (multiple rows in `invoice_lines`).

### Invoice Line
A single product entry within an invoice. Defined by (`InvoiceNo`, `StockCode`).
Contains `Quantity` and `UnitPrice` for that product on that transaction.

### Customer
An individual buyer identified by a `CustomerID` (numeric). Not all transactions
are linked to a customer  -  where `CustomerID` is NULL the purchase was made by an
unregistered or guest buyer. NULL customer rows are valid sales but cannot be
attributed to a named customer for segmentation or loyalty analysis.

### Product
An item sold by the retailer, identified by `StockCode`. The human-readable name
is in `Description`. A single `StockCode` may have minor description variations
across invoices; the canonical description is whichever appears most frequently
for that code.

---

## Key Terms

### Return / Cancellation
A **return** in this dataset is identified by one of two signals:
1. The `InvoiceNo` begins with **'C'** (cancellation invoice).
2. The `Quantity` on a line is **negative**.

Both signals should be treated as returns when calculating net revenue or return
rates. There is no separate `Returns` column in the source data.

> Example: `InvoiceNo = 'C536379'` with `Quantity = -6` is a cancellation of 6
> units of a previously purchased product.

### Revenue (Gross)
Total money received from sales **before** deducting returns.

```
Gross Revenue = SUM(Quantity * UnitPrice)
```

Applied to all rows regardless of whether they are cancellations. Because
cancellation rows have negative `Quantity`, gross revenue already partially
nets them out when summed over a period.

### Revenue (Net)
Total money received **excluding** all cancellation / return transactions.

```
Net Revenue = SUM(Quantity * UnitPrice)
             WHERE Quantity > 0
               AND InvoiceNo NOT LIKE 'C%'
```

This is the preferred revenue figure for performance reporting.

### Gross Margin / Profit Margin
**Cannot be calculated from this dataset.** The source data contains no cost
(`COGS`) column. Revenue figures are available but cost of goods is not. Any
margin figure would require a synthetic cost assumption  -  treat such calculations
as estimates, not actuals.

### Active Customer
A customer who placed **at least one non-cancelled invoice** in the period of
interest. Customers who only appear on cancellation invoices in a period are not
counted as active in that period.

```
Active = CustomerID IS NOT NULL
         AND InvoiceNo NOT LIKE 'C%'
         AND Quantity > 0
```

> Alternative definition used in segment analysis: customers in the **top 20%
> by order count** are classified as "relatively active" / high-engagement
> customers. Both definitions are valid depending on the business question.

### Repeat / Loyal Customer
A customer with **more than one distinct invoice** in the period. Measured by
counting unique `InvoiceNo` values per `CustomerID`.

### New Customer
For this dataset, a new customer in a given month is one whose **earliest
invoice date** falls within that month. Because the data starts in December 2010,
all customers seen in December 2010 are technically "new"  -  interpret month-on-
month new-customer counts with this in mind.

### Guest Transaction
A transaction row where `CustomerID IS NULL`. These represent purchases made
without a registered account  -  approximately **24% of all transaction rows**.
Guest transaction revenue is included in aggregate totals but excluded from
any per-customer analysis (CLV, retention, repeat rate).

---

## Derived Segments

### UK vs International
The `Country` column on the `customers` table indicates where the customer is
based. Approximately **84% of revenue** comes from **United Kingdom** customers.
The remaining 16% is split across ~37 other countries. UK customers are the
primary segment for trend analysis.

### High-Value Customer (HVC)
No formal threshold is defined in the source data. A common convention:
customers in the top decile (top 10%) by total net revenue over the full period.

### B2B Wholesale Context
The dataset represents a UK-based online retailer supplying **wholesale / trade
customers** (businesses, not individual consumers). Many `CustomerID`s represent
resellers buying in bulk. This is relevant when interpreting large `Quantity`
values on a single invoice  -  they are normal for this dataset and reflect bulk
wholesale orders, not individual consumer purchases.

---

## Time Scope

The data covers transactions from **1 December 2010 to 9 December 2011**
(approximately 12 months, not a full calendar year 2011).

- **Year-over-year comparison is not meaningful**  -  there is only ~1 year of data.
- **Month-over-month growth** is the appropriate growth metric for this dataset.
- Monthly and quarterly trends are valid.
- December 2010 and December 2011 are both partial months in the data.

---

## Currency

All prices (`UnitPrice`) and therefore all revenue figures are in
**British Pounds Sterling (GBP, GBP)**. No currency conversion data is included.
International customers (France, Germany, Netherlands, etc.) pay in GBP at the
price listed  -  no multi-currency pricing is present in the dataset.
