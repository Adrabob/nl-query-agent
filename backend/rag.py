"""Retrieval-Augmented Generation over project documents.

Pipeline:
  1. Embed the user question with OCI GenAI Cohere Embed v3 (SEARCH_QUERY type).
  2. Run VECTOR_DISTANCE search over docs_chunks to retrieve top-k chunks.
  3. Send retrieved context + question to the LLM for a grounded answer.
  4. Return (answer, sources).

Authentication: tries Instance Principal first (OCI Compute), falls back to
~/.oci/config API key (local development). No other auth methods are used.
"""

import json
from functools import lru_cache

import oci
import oci.auth.signers
from oci.generative_ai_inference import GenerativeAiInferenceClient
from oci.generative_ai_inference.models import (
    ChatDetails,
    CohereChatRequest,
    EmbedTextDetails,
    OnDemandServingMode,
)

import backend.config as config
from backend.db import get_pool

TOP_K = 3
MAX_ANSWER_TOKENS = 512

_SYSTEM_PROMPT = (
    "You are a helpful business intelligence assistant for a UK-based online retail company. "
    "Answer the user's question based ONLY on the provided document excerpts. "
    "If the answer is not fully covered by the excerpts, say so clearly — never invent data. "
    "Be concise and factual."
)


# ── OCI GenAI client ──────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _genai_endpoint() -> str:
    return f"https://inference.generativeai.{config.OCI_REGION}.oci.oraclecloud.com"


def _build_client() -> GenerativeAiInferenceClient:
    endpoint = _genai_endpoint()
    try:
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        return GenerativeAiInferenceClient(
            config={},
            signer=signer,
            service_endpoint=endpoint,
        )
    except Exception:
        cfg = oci.config.from_file()
        cfg["region"] = config.OCI_REGION
        return GenerativeAiInferenceClient(
            config=cfg,
            service_endpoint=endpoint,
        )


_client: GenerativeAiInferenceClient | None = None


def _get_client() -> GenerativeAiInferenceClient:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed_question(question: str) -> list[float]:
    """Embed a single question string with SEARCH_QUERY input type."""
    response = _get_client().embed_text(
        EmbedTextDetails(
            inputs=[question],
            serving_mode=OnDemandServingMode(model_id=config.OCI_EMBEDDING_MODEL),
            compartment_id=config.OCI_COMPARTMENT_OCID,
            input_type="SEARCH_QUERY",
        )
    )
    return response.data.embeddings[0]


# ── Vector retrieval ──────────────────────────────────────────────────────────

def _retrieve_chunks(embedding: list[float], top_k: int = TOP_K) -> list[dict]:
    """Query docs_chunks with VECTOR_DISTANCE and return the nearest chunks."""
    embedding_json = json.dumps(embedding)
    sql = """
        SELECT chunk_id,
               doc_name,
               DBMS_LOB.SUBSTR(chunk_text, 2000, 1) AS chunk_text,
               VECTOR_DISTANCE(embedding, TO_VECTOR(:vec), COSINE) AS distance
        FROM   docs_chunks
        ORDER  BY distance ASC
        FETCH  FIRST :k ROWS ONLY
    """
    pool = get_pool()
    with pool.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, vec=embedding_json, k=top_k)
            rows = cur.fetchall()

    return [
        {
            "chunk_id": row[0],
            "doc_name": row[1],
            "chunk_text": row[2] if isinstance(row[2], str) else row[2].read(),
            "distance": float(row[3]),
        }
        for row in rows
    ]


# ── Answer generation ─────────────────────────────────────────────────────────

def _generate_answer(question: str, chunks: list[dict]) -> str:
    """Produce a grounded answer from the LLM given retrieved chunks as context."""
    context_parts = [
        f"[Source: {c['doc_name']}]\n{c['chunk_text']}"
        for c in chunks
    ]
    context = "\n\n---\n\n".join(context_parts)

    user_message = (
        f"Document excerpts:\n\n{context}\n\n"
        f"Question: {question}"
    )

    response = _get_client().chat(
        ChatDetails(
            serving_mode=OnDemandServingMode(model_id=config.OCI_GENAI_MODEL),
            compartment_id=config.OCI_COMPARTMENT_OCID,
            chat_request=CohereChatRequest(
                message=user_message,
                preamble_override=_SYSTEM_PROMPT,
                max_tokens=MAX_ANSWER_TOKENS,
                temperature=0.1,
                is_stream=False,
            ),
        )
    )
    return response.data.chat_response.text


# ── Public API ────────────────────────────────────────────────────────────────

def ask_docs(question: str) -> tuple[str, list[dict]]:
    """Full RAG pipeline: embed → retrieve → generate.

    Returns:
        answer  — LLM-generated answer grounded in retrieved chunks.
        sources — list of {doc, snippet} dicts (one per retrieved chunk).
    Raises:
        Any OCI / DB exception is propagated; the caller (main.py) handles it.
    """
    embedding = _embed_question(question)
    chunks = _retrieve_chunks(embedding, top_k=TOP_K)

    if not chunks:
        return (
            "I couldn't find any relevant information in the documents for that question. "
            "Try /query for questions about sales, customers, products, or invoices.",
            [],
        )

    answer = _generate_answer(question, chunks)
    sources = [
        {"doc": c["doc_name"], "snippet": c["chunk_text"][:300]}
        for c in chunks
    ]
    return answer, sources
