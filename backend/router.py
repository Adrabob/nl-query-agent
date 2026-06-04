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
- docs: looks up definitions, formulas, methodology, AND the dataset's limitations
  (what it cannot answer) from knowledge documents

Route to docs when the question needs a definition/methodology OR asks for data the
dataset does NOT contain. The dataset is ~12 months of sales transactions only; it has
NO data on:
- profit, margin, cost, or COGS (only selling price is recorded)
- inventory or current stock levels (only what was sold, not what is in stock)
- customer demographics such as age or gender
- year-over-year or any multi-year comparison (data spans ~1 year)
- future predictions, forecasts, or churn/retention risk
- shipping, delivery, or logistics
- product categories or hierarchy
- discounts or list prices

Default to sql. Choose sql whenever the question can be answered by counting, summing,
ranking, averaging, or filtering the recorded sales — even if it mentions revenue, net
revenue, returns, repeat purchases, or month-over-month growth.

Examples:
"how many customers do we have?" → sql
"what is total net revenue by country?" → sql
"top 5 products by units sold" → sql
"which products do customers come back to buy again?" → sql
"which products have the highest return rate?" → sql
"month over month revenue growth by country" → sql
"which month had the highest revenue in 2011?" → sql
"what counts as a return in this dataset?" → docs
"how is average order value defined?" → docs
"what currency are the prices in?" → docs
"can we calculate gross margin?" → docs
"what is our gross margin by product?" → docs
"what was our year over year revenue growth?" → docs
"what are our current stock levels?" → docs
"what is the age and gender breakdown of our customers?" → docs
"which customers are at risk of churning?" → docs
"predict next month's revenue" → docs

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
