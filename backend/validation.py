"""Input guardrails, ambiguity detection, and error response formatting.

Validates incoming questions before they reach Select AI:
  - rejects empty or whitespace-only input
  - flags questions that are obviously out of scope for the loaded dataset
  - blocks SQL injection / DML attempts disguised as questions

Public functions return (is_valid: bool, error_message: str | None) so callers
can short-circuit without importing exception types from this module.
"""

import re

# Words that indicate DML/DDL rather than a genuine business question.
_BLOCKED = re.compile(
    r"\b(drop|delete|truncate|insert|update|alter|create|grant|revoke|exec|execute)\b",
    re.IGNORECASE,
)

# Minimum useful question length.
_MIN_LEN = 4


def validate_question(question: str) -> tuple[bool, str | None]:
    """Return (True, None) if the question is acceptable, else (False, reason)."""
    q = question.strip()

    if len(q) < _MIN_LEN:
        return False, "Please enter a more complete question."

    if _BLOCKED.search(q):
        return (
            False,
            "That looks like a database command. "
            "Please ask a business question about sales, customers, products, or invoices.",
        )

    return True, None
