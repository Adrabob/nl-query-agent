"""Load UCI Online Retail CSV into the four normalized Oracle tables.

Run once after sql/01_schema.sql has been executed.
Usage:
    uv run python scripts/load_data.py
"""

import csv
import os
from datetime import datetime
from dotenv import load_dotenv
import oracledb

load_dotenv()

CSV_PATH = "data/dataset/data.csv"
DATE_FMT = "%m/%d/%Y %H:%M"
BATCH_SIZE = 500


def _parse_customer_id(value: str):
    v = value.strip()
    if not v:
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def _connect():
    wallet = os.getenv("WALLET_DIR")
    return oracledb.connect(
        user=os.getenv("ADB_USERNAME"),
        password=os.getenv("ADB_PASSWORD"),
        dsn=os.getenv("ADB_CONNECTION_STRING"),
        config_dir=wallet,
        wallet_location=wallet,
        wallet_password=os.getenv("WALLET_PASSWORD"),
    )


def _insert_batches(cur, conn, sql: str, data: list, label: str) -> None:
    total = len(data)
    for i in range(0, total, BATCH_SIZE):
        cur.executemany(sql, data[i : i + BATCH_SIZE])
        conn.commit()
        print(f"  {label}: {min(i + BATCH_SIZE, total):,}/{total:,}", end="\r")
    print(f"  {label}: {total:,}/{total:,} done   ")


def main():
    print("Reading CSV...")
    customers: dict[int, str] = {}
    products: dict[str, str] = {}
    invoices: dict[str, tuple] = {}
    lines: list[tuple] = []

    with open(CSV_PATH, encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            invoice_no  = row["InvoiceNo"].strip()
            stock_code  = row["StockCode"].strip()
            description = row["Description"].strip()
            country     = row["Country"].strip()
            customer_id = _parse_customer_id(row["CustomerID"])

            if not invoice_no or not stock_code:
                continue

            try:
                quantity   = int(row["Quantity"].strip())
                unit_price = float(row["UnitPrice"].strip())
                inv_date   = datetime.strptime(row["InvoiceDate"].strip(), DATE_FMT)
            except (ValueError, KeyError):
                continue

            if customer_id is not None and customer_id not in customers:
                customers[customer_id] = country

            if stock_code not in products:
                products[stock_code] = description or stock_code

            if invoice_no not in invoices:
                invoices[invoice_no] = (inv_date, customer_id)

            lines.append((invoice_no, stock_code, quantity, unit_price))

    print(f"  customers : {len(customers):,}")
    print(f"  products  : {len(products):,}")
    print(f"  invoices  : {len(invoices):,}")
    print(f"  lines     : {len(lines):,}")

    print("\nConnecting to database...")
    conn = _connect()
    cur = conn.cursor()

    print("Inserting customers...")
    _insert_batches(cur, conn,
        "INSERT INTO customers (customer_id, country) VALUES (:1, :2)",
        list(customers.items()), "customers")

    print("Inserting products...")
    _insert_batches(cur, conn,
        "INSERT INTO products (stock_code, description) VALUES (:1, :2)",
        list(products.items()), "products")

    print("Inserting invoices...")
    _insert_batches(cur, conn,
        "INSERT INTO invoices (invoice_no, invoice_date, customer_id) VALUES (:1, :2, :3)",
        [(ino, dt, cid) for ino, (dt, cid) in invoices.items()], "invoices")

    print("Inserting invoice_lines...")
    _insert_batches(cur, conn,
        "INSERT INTO invoice_lines (invoice_no, stock_code, quantity, unit_price) VALUES (:1, :2, :3, :4)",
        lines, "invoice_lines")

    cur.close()
    conn.close()
    print("\nLoad complete.")


if __name__ == "__main__":
    main()
