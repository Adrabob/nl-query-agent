"""Oracle Autonomous Database connection pool and low-level query helpers.

Uses oracledb thin mode (no Oracle Instant Client required). Wallet-based mTLS:
both config_dir and wallet_location must point to the wallet directory so that
oracledb can locate tnsnames.ora and the client certificate.

All callers receive plain Python objects — no oracledb types leak out of this module.
"""

import datetime
import decimal
import re
from typing import Any

_SQL_COMMENT = re.compile(r'--[^\n]*')

import oracledb

import backend.config as config

_pool: oracledb.ConnectionPool | None = None


def get_pool() -> oracledb.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = oracledb.create_pool(
            user=config.ADB_USERNAME,
            password=config.ADB_PASSWORD,
            dsn=config.ADB_CONNECTION_STRING,
            config_dir=config.WALLET_DIR,
            wallet_location=config.WALLET_DIR,
            wallet_password=config.WALLET_PASSWORD,
            min=1,
            max=5,
            increment=1,
        )
    return _pool


def _serialize(value: Any) -> Any:
    """Convert Oracle-specific types to JSON-safe Python primitives."""
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if hasattr(value, "read"):
        return value.read()
    return value


def execute_select(sql: str) -> tuple[list[str], list[list[Any]]]:
    """Run a SELECT statement and return (column_names, rows)."""
    # Strip -- comments: Select AI sometimes adds inline notes that contain
    # colon-prefixed words oracledb misreads as bind variable placeholders.
    sql = _SQL_COMMENT.sub('', sql)
    pool = get_pool()
    with pool.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [col[0] for col in cur.description]
            rows = [
                [_serialize(v) for v in row]
                for row in cur.fetchmany(numRows=500)
            ]
            return columns, rows


def execute_generate(prompt: str, action: str) -> str:
    """Call DBMS_CLOUD_AI.GENERATE and return the result as a plain string."""
    pool = get_pool()
    with pool.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DBMS_CLOUD_AI.GENERATE("
                "  prompt       => :p,"
                "  profile_name => :prof,"
                "  action       => :a"
                ") FROM DUAL",
                p=prompt,
                prof=config.SELECT_AI_PROFILE,
                a=action,
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                return ""
            val = row[0]
            return val.read() if hasattr(val, "read") else str(val)
