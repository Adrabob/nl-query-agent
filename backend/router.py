"""LLM-based intent classifier for routing user questions.

classify(question) returns "sql" for database queries or "docs" for document lookups.
Uses the same OCI GenAI client singleton as rag.py — no second client is created.
"""

from oci.generative_ai_inference.models import (
    ChatDetails,
    CohereChatRequest,
    OnDemandServingMode,
)

import backend.config as config
from backend.rag import _get_client

_CLASSIFIER_PROMPT = """\
You are a routing assistant for a retail analytics AI system.
The system has two tools:
- sql: queries a live sales database (customers, invoices, products, revenue, quantities, countries, dates)
- docs: looks up definitions, formulas, data limitations, and methodology from knowledge documents

Examples:
"how many customers do we have?" → sql
"what is the total revenue by country?" → sql
"show me top 5 products by units sold" → sql
"what counts as a return in this dataset?" → docs
"can we calculate gross margin?" → docs
"how is average order value defined?" → docs
"what currency are the prices in?" → docs
"which month had the highest revenue in 2011?" → sql

Classify the following question. Reply with exactly one word: sql or docs

Question: {question}\
"""


def classify(question: str) -> str:
    """Return "sql" or "docs" for the given question. Defaults to "sql" on any unexpected output."""
    prompt = _CLASSIFIER_PROMPT.format(question=question)
    response = _get_client().chat(
        ChatDetails(
            serving_mode=OnDemandServingMode(model_id=config.OCI_GENAI_MODEL),
            compartment_id=config.OCI_COMPARTMENT_OCID,
            chat_request=CohereChatRequest(
                message=prompt,
                temperature=0,
                max_tokens=5,
                is_stream=False,
            ),
        )
    )
    result = response.data.chat_response.text.strip().lower()
    if result in ("sql", "docs"):
        return result
    return "sql"
