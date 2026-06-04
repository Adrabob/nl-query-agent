"""In-memory multi-turn conversation state, keyed by session_id.

Stores the last question, generated SQL, and result rows for each active
session so that follow-up queries ("now just the UK ones") can be resolved
by re-sending the prior context to Select AI.

State is process-local and non-persistent: it resets on server restart.
For a production system this would be backed by Redis or a DB table.
"""

from dataclasses import dataclass, field
from typing import Any

_MAX_SESSIONS = 1000  # cap to avoid unbounded memory growth


@dataclass
class SessionState:
    last_question: str = ""
    last_sql: str = ""
    last_columns: list[str] = field(default_factory=list)
    last_rows: list[list[Any]] = field(default_factory=list)


_sessions: dict[str, SessionState] = {}


def get_session(session_id: str) -> SessionState:
    if session_id not in _sessions:
        if len(_sessions) >= _MAX_SESSIONS:
            # Evict oldest entry when cap is reached.
            oldest = next(iter(_sessions))
            del _sessions[oldest]
        _sessions[session_id] = SessionState()
    return _sessions[session_id]


def update_session(
    session_id: str,
    question: str,
    sql: str,
    columns: list[str],
    rows: list[list[Any]],
) -> None:
    state = get_session(session_id)
    state.last_question = question
    state.last_sql = sql
    state.last_columns = columns
    state.last_rows = rows


def build_contextual_question(session_id: str, question: str) -> str:
    """Prepend prior context so Select AI can resolve follow-up pronouns."""
    state = get_session(session_id)
    if not state.last_sql:
        return question

    parts = [
        f"Previous question: {state.last_question}",
        f"Previous SQL: {state.last_sql}",
    ]

    if state.last_columns and state.last_rows:
        header = ", ".join(state.last_columns)
        # Include up to 20 rows so Select AI knows the exact result set
        rows_preview = "\n".join(
            ", ".join(str(v) for v in row)
            for row in state.last_rows[:20]
        )
        parts.append(f"Previous result ({len(state.last_rows)} rows):\n{header}\n{rows_preview}")

    parts.append(f"Follow-up: {question}")
    return "\n".join(parts)
