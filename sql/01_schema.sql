-- Normalized schema for UCI Online Retail dataset.
-- Column COMMENTs and FK constraints improve Select AI accuracy.
-- Run as NLQUERYUSER in SQL Developer Web before loading data.

-- ------------------------------------------------------------
-- CUSTOMERS
-- ------------------------------------------------------------
CREATE TABLE customers (
    customer_id   NUMBER        NOT NULL,
    country       VARCHAR2(100) NOT NULL,
    CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);

COMMENT ON TABLE  customers              IS 'Unique customers. One customer may appear across many invoices.';
COMMENT ON COLUMN customers.customer_id IS 'Numeric customer identifier. Anonymous transactions have no customer row.';
COMMENT ON COLUMN customers.country     IS 'Country where the customer is located, e.g. United Kingdom, France, Germany.';

-- ------------------------------------------------------------
-- PRODUCTS
-- ------------------------------------------------------------
CREATE TABLE products (
    stock_code    VARCHAR2(20)  NOT NULL,
    description   VARCHAR2(255),
    CONSTRAINT pk_products PRIMARY KEY (stock_code)
);

COMMENT ON TABLE  products              IS 'Unique products sold by the retailer.';
COMMENT ON COLUMN products.stock_code   IS 'Alphanumeric product code, e.g. 85123A.';
COMMENT ON COLUMN products.description  IS 'Plain-English product name, e.g. WHITE HANGING HEART T-LIGHT HOLDER.';

-- ------------------------------------------------------------
-- INVOICES
-- ------------------------------------------------------------
CREATE TABLE invoices (
    invoice_no    VARCHAR2(20)  NOT NULL,
    invoice_date  DATE          NOT NULL,
    customer_id   NUMBER,
    CONSTRAINT pk_invoices          PRIMARY KEY (invoice_no),
    CONSTRAINT fk_invoices_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

COMMENT ON TABLE  invoices              IS 'Each row is one transaction. Invoices prefixed with C are cancellations or returns.';
COMMENT ON COLUMN invoices.invoice_no   IS 'Invoice identifier. Normal invoices are six-digit numbers such as 536370. Cancellation invoices start with the letter C followed by digits such as C536379. To find cancellations, filter where INVOICE_NO starts with the letter C.';
COMMENT ON COLUMN invoices.invoice_date IS 'Date and time of the transaction. Data spans December 2010 to December 2011.';
COMMENT ON COLUMN invoices.customer_id  IS 'Customer who placed the order. NULL for anonymous or guest transactions.';

-- ------------------------------------------------------------
-- INVOICE_LINES
-- ------------------------------------------------------------
CREATE TABLE invoice_lines (
    line_id       NUMBER GENERATED ALWAYS AS IDENTITY,
    invoice_no    VARCHAR2(20)  NOT NULL,
    stock_code    VARCHAR2(20)  NOT NULL,
    quantity      NUMBER        NOT NULL,
    unit_price    NUMBER(10,2)  NOT NULL,
    CONSTRAINT pk_invoice_lines  PRIMARY KEY (line_id),
    CONSTRAINT fk_lines_invoice  FOREIGN KEY (invoice_no) REFERENCES invoices  (invoice_no),
    CONSTRAINT fk_lines_product  FOREIGN KEY (stock_code) REFERENCES products  (stock_code)
);

COMMENT ON TABLE  invoice_lines              IS 'Line items within each invoice. Revenue = quantity * unit_price. Negative quantity means a returned item.';
COMMENT ON COLUMN invoice_lines.invoice_no   IS 'Parent invoice reference.';
COMMENT ON COLUMN invoice_lines.stock_code   IS 'Product sold on this line.';
COMMENT ON COLUMN invoice_lines.quantity     IS 'Units sold. Negative values indicate returns or cancellation lines.';
COMMENT ON COLUMN invoice_lines.unit_price   IS 'Price per unit in GBP at time of sale.';
