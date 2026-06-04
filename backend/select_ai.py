"""Select AI wrapper for Oracle DBMS_CLOUD_AI actions.

Exposes four actions against the configured Select AI profile:
  showsql    — translate a natural-language question to SQL without executing it
  runsql     — translate and execute (via showsql + our own execute_select)
  narrate    — translate, execute, and narrate the result in plain English
  explainsql — explain an existing SQL statement in plain English

All methods return plain Python types; database details are handled by db.py.
"""

import json

from backend.db import execute_generate, execute_select


def showsql(question: str) -> str:
    """Return the SQL that Select AI would run for the given question."""
    return execute_generate(question, "showsql").strip()


def run_query(question: str) -> tuple[str, list[str], list]:
    """Translate question → SQL → execute. Returns (sql, columns, rows)."""
    sql = showsql(question)
    if not sql:
        raise ValueError("Select AI returned no SQL for this question.")
    columns, rows = execute_select(sql)
    return sql, columns, rows


def narrate(question: str) -> str:
    """Return a plain-English narrative of the query result."""
    raw = execute_generate(question, "narrate")
    # narrate action returns JSON: {"result_text": "..."}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data.get("result_text") or data.get("text") or raw
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                return next(iter(first.values()), raw)
    except (json.JSONDecodeError, TypeError):
        pass
    return raw


def explainsql(sql: str) -> str:
    """Return a plain-English explanation of the given SQL statement."""
    return execute_generate(sql, "explainsql").strip()
