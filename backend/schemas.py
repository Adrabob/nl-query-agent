"""Pydantic request/response models for all API endpoints.

This module is the API contract between the backend and frontend.
Do not change field names or types without coordinating with the frontend owner.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# /query  — natural language → SQL → result table
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question from the user")
    session_id: str = Field(..., description="Opaque session identifier for multi-turn state")


class QueryResponse(BaseModel):
    generated_sql: str = Field(default="", description="SQL produced by Select AI (shown in UI for transparency)")
    columns: list[str] = Field(default_factory=list, description="Ordered list of column names")
    rows: list[list] = Field(default_factory=list, description="Result rows; each row is a list of values")
    row_count: int = Field(default=0, description="Number of rows returned")
    error: Optional[str] = Field(default=None, description="Error code/type when the request failed; null on success")
    message: Optional[str] = Field(default=None, description="Human-readable explanation when error is set")


# ---------------------------------------------------------------------------
# /explain  — explain an SQL query or a natural-language question
# ---------------------------------------------------------------------------

class ExplainRequest(BaseModel):
    sql: Optional[str] = Field(default=None, description="Raw SQL to explain (mutually exclusive with question)")
    question: Optional[str] = Field(default=None, description="Natural-language question to explain (mutually exclusive with sql)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"sql": "SELECT COUNT(*) FROM invoices WHERE Country = 'Germany'"},
                {"question": "How many invoices came from Germany?"},
            ]
        }
    }


class ExplainResponse(BaseModel):
    explanation: str = Field(..., description="Plain-English breakdown of the query or question")


# ---------------------------------------------------------------------------
# /summarize  — narrate the most recent query result for a session
# ---------------------------------------------------------------------------

class SummarizeRequest(BaseModel):
    session_id: str = Field(..., description="Session whose last result should be summarized")


class SummarizeResponse(BaseModel):
    summary: str = Field(..., description="Narrative summary of the last query result")


# ---------------------------------------------------------------------------
# /ask_docs  — RAG over related documents via Oracle AI Vector Search
# ---------------------------------------------------------------------------

class DocSource(BaseModel):
    doc: str = Field(..., description="Document name or identifier")
    snippet: str = Field(..., description="The retrieved text chunk used to answer the question")


class AskDocsRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question to answer from documents")
    session_id: str = Field(..., description="Session identifier (used for conversation context)")


class AskDocsResponse(BaseModel):
    answer: str = Field(..., description="Grounded answer generated from retrieved document chunks")
    sources: list[DocSource] = Field(default_factory=list, description="Document chunks used to produce the answer")


# ---------------------------------------------------------------------------
# /chat  — unified endpoint: classifies intent then routes to sql or docs
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question from the user")
    session_id: str = Field(..., description="Opaque session identifier for multi-turn state")


class ChatResponse(BaseModel):
    route: str = Field(..., description="Classified route: 'sql' or 'docs'")
    generated_sql: Optional[str] = Field(default=None, description="SQL produced by Select AI (sql route only)")
    columns: Optional[list[str]] = Field(default=None, description="Result column names (sql route only)")
    rows: Optional[list[list]] = Field(default=None, description="Result rows (sql route only)")
    row_count: Optional[int] = Field(default=None, description="Number of rows returned (sql route only)")
    answer: Optional[str] = Field(default=None, description="Grounded answer from documents (docs route only)")
    sources: Optional[list[DocSource]] = Field(default=None, description="Document sources (docs route only)")
    error: Optional[str] = Field(default=None, description="Error code when the request failed; null on success")
    message: Optional[str] = Field(default=None, description="Human-readable error text when error is set")


# ---------------------------------------------------------------------------
# /health  — liveness check
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Always 'ok' when the service is running")
