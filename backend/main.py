"""FastAPI application entry point.

Defines the app instance and registers all route handlers.
Each handler delegates to the relevant module; business logic does not live here.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

from backend import rag, router, select_ai, session, validation
from backend.schemas import (
    AskDocsRequest,
    AskDocsResponse,
    ChatRequest,
    ChatResponse,
    DocSource,
    ExplainRequest,
    ExplainResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SummarizeRequest,
    SummarizeResponse,
)

app = FastAPI(title="NL Query Agent", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    ok, msg = validation.validate_question(req.question)
    if not ok:
        return QueryResponse(error="INVALID_INPUT", message=msg)

    contextual_q = session.build_contextual_question(req.session_id, req.question)

    try:
        sql, columns, rows = select_ai.run_query(contextual_q)
    except Exception as exc:
        return QueryResponse(
            error="QUERY_FAILED",
            message=_user_message(exc),
        )

    session.update_session(req.session_id, req.question, sql, columns, rows)
    return QueryResponse(
        generated_sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
    )


@app.post("/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest) -> ExplainResponse:
    try:
        if req.sql:
            text = select_ai.explainsql(req.sql)
        elif req.question:
            sql = select_ai.showsql(req.question)
            text = select_ai.explainsql(sql)
        else:
            return ExplainResponse(explanation="Provide either 'sql' or 'question'.")
        return ExplainResponse(explanation=text)
    except Exception as exc:
        return ExplainResponse(explanation=f"Could not explain: {_user_message(exc)}")


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest) -> SummarizeResponse:
    state = session.get_session(req.session_id)
    if not state.last_question:
        return SummarizeResponse(summary="No previous query found for this session.")
    try:
        summary = select_ai.narrate(state.last_question)
        return SummarizeResponse(summary=summary)
    except Exception as exc:
        return SummarizeResponse(summary=f"Could not summarize: {_user_message(exc)}")


@app.post("/ask_docs", response_model=AskDocsResponse)
def ask_docs(req: AskDocsRequest) -> AskDocsResponse:
    ok, msg = validation.validate_question(req.question)
    if not ok:
        return AskDocsResponse(answer=msg, sources=[])
    try:
        answer, sources = rag.ask_docs(req.question)
        return AskDocsResponse(
            answer=answer,
            sources=[DocSource(doc=s["doc"], snippet=s["snippet"]) for s in sources],
        )
    except Exception as exc:
        return AskDocsResponse(
            answer=f"Could not search documents: {_user_message(exc)}",
            sources=[],
        )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    ok, msg = validation.validate_question(req.question)
    if not ok:
        return ChatResponse(route="sql", error="INVALID_INPUT", message=msg)

    route = router.classify(req.question)

    if route == "docs":
        try:
            answer, sources = rag.ask_docs(req.question)
            return ChatResponse(
                route="docs",
                answer=answer,
                sources=[DocSource(doc=s["doc"], snippet=s["snippet"]) for s in sources],
            )
        except Exception as exc:
            return ChatResponse(
                route="docs",
                error="DOCS_FAILED",
                message=_user_message(exc),
            )

    # route == "sql"
    contextual_q = session.build_contextual_question(req.session_id, req.question)
    try:
        sql, columns, rows = select_ai.run_query(contextual_q)
    except Exception as exc:
        return ChatResponse(
            route="sql",
            error="QUERY_FAILED",
            message=_user_message(exc),
        )

    session.update_session(req.session_id, req.question, sql, columns, rows)
    narration = None
    if not rows:
        try:
            narration = select_ai.narrate(contextual_q)
        except Exception:
            narration = "No results found for that query."
    return ChatResponse(
        route="sql",
        generated_sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        message=narration,
    )


def _user_message(exc: Exception) -> str:
    logger.exception("Request failed: %s", exc)
    msg = str(exc)
    if "ORA-" in msg:
        return (
            "The database couldn't process that question. "
            "Try rephrasing or asking about sales, customers, products, or invoices."
        )
    return "An unexpected error occurred. Please try again."


# Serve the static frontend from the same origin (no CORS, single deploy).
# Mounted last so the API routes above and FastAPI's /docs keep precedence;
# all other paths (/, /index.css, images) are served from the frontend folder.
_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
