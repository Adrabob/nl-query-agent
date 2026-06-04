"""One-time script: chunk the RAG documents, embed them with OCI GenAI
Cohere Embed v3, and insert the results into the docs_chunks table.

Run from the project root after sql/04_vector_setup.sql has been executed:

    uv run scripts/embed_docs.py

Prerequisites:
  - ~/.oci/config exists with a valid API key profile for uk-london-1
  - .env is populated (ADB connection settings)
  - NLQUERYUSER.DOCS_CHUNKS table already created (04_vector_setup.sql)

The script is idempotent: it clears existing rows for each document before
re-inserting, so it is safe to re-run after editing a document.
"""

import json
import os
import re
import sys
from pathlib import Path

import oci
import oracledb
from dotenv import load_dotenv
from oci.generative_ai_inference import GenerativeAiInferenceClient
from oci.generative_ai_inference.models import EmbedTextDetails, OnDemandServingMode

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent.parent / "data" / "docs"

OCI_REGION = os.getenv("OCI_REGION", "uk-london-1")
OCI_COMPARTMENT_OCID = os.getenv("OCI_COMPARTMENT_OCID", "")
OCI_EMBEDDING_MODEL = os.getenv(
    "OCI_EMBEDDING_MODEL", "cohere.embed-multilingual-v3.0"
)
GENAI_ENDPOINT = f"https://inference.generativeai.{OCI_REGION}.oci.oraclecloud.com"

ADB_USERNAME = os.getenv("ADB_USERNAME", "")
ADB_PASSWORD = os.getenv("ADB_PASSWORD", "")
ADB_CONNECTION_STRING = os.getenv("ADB_CONNECTION_STRING", "")
WALLET_DIR = os.getenv("WALLET_DIR", "")
WALLET_PASSWORD = os.getenv("WALLET_PASSWORD", "")

# Maximum characters per chunk (Cohere Embed v3 token limit ~512, ~2000 chars is safe)
MAX_CHUNK_CHARS = 2000
# Minimum characters — skip chunks shorter than this (usually stray lines)
MIN_CHUNK_CHARS = 80
# OCI GenAI maximum inputs per embed request
EMBED_BATCH_SIZE = 20


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_markdown(text: str, doc_name: str) -> list[dict]:
    """Split a markdown document into chunks by H2/H3 sections.

    Returns a list of dicts: {doc_name, chunk_text}.
    """
    # Split on lines that start with ## or ###
    section_pattern = re.compile(r"^(#{2,3} .+)$", re.MULTILINE)
    parts = section_pattern.split(text)

    chunks: list[dict] = []

    # parts alternates: [preamble, header, body, header, body, ...]
    # Index 0 is text before the first header (document title + intro)
    i = 0
    pending_header = ""

    for part in parts:
        part = part.strip()
        if not part:
            i += 1
            continue

        if section_pattern.match(part):
            pending_header = part
        else:
            # Combine header with its body
            combined = (pending_header + "\n\n" + part).strip() if pending_header else part
            pending_header = ""

            # If the combined chunk is too long, split on blank lines
            if len(combined) > MAX_CHUNK_CHARS:
                paragraphs = re.split(r"\n{2,}", combined)
                current = ""
                for para in paragraphs:
                    if len(current) + len(para) + 2 > MAX_CHUNK_CHARS and current:
                        if len(current) >= MIN_CHUNK_CHARS:
                            chunks.append({"doc_name": doc_name, "chunk_text": current.strip()})
                        current = para
                    else:
                        current = (current + "\n\n" + para).strip() if current else para
                if current and len(current) >= MIN_CHUNK_CHARS:
                    chunks.append({"doc_name": doc_name, "chunk_text": current.strip()})
            else:
                if len(combined) >= MIN_CHUNK_CHARS:
                    chunks.append({"doc_name": doc_name, "chunk_text": combined})

        i += 1

    return chunks


def load_chunks() -> list[dict]:
    """Read all .md files from DOCS_DIR and return all chunks."""
    all_chunks: list[dict] = []
    md_files = sorted(DOCS_DIR.glob("*.md"))

    if not md_files:
        print(f"ERROR: No .md files found in {DOCS_DIR}", file=sys.stderr)
        sys.exit(1)

    for path in md_files:
        text = path.read_text(encoding="utf-8")
        doc_chunks = chunk_markdown(text, path.name)
        print(f"  {path.name}: {len(doc_chunks)} chunks")
        all_chunks.extend(doc_chunks)

    return all_chunks


# ── Embedding ─────────────────────────────────────────────────────────────────

def build_genai_client() -> GenerativeAiInferenceClient:
    """Build the OCI GenAI client using the default API key config (~/.oci/config)."""
    try:
        cfg = oci.config.from_file()
        cfg["region"] = OCI_REGION
        return GenerativeAiInferenceClient(
            config=cfg,
            service_endpoint=GENAI_ENDPOINT,
        )
    except Exception as exc:
        print(f"ERROR: Could not load OCI config: {exc}", file=sys.stderr)
        print("Ensure ~/.oci/config exists with a valid API key profile.", file=sys.stderr)
        sys.exit(1)


def embed_batch(client: GenerativeAiInferenceClient, texts: list[str]) -> list[list[float]]:
    """Call OCI GenAI to embed a batch of texts. Returns list of float vectors."""
    if not OCI_COMPARTMENT_OCID:
        print("ERROR: OCI_COMPARTMENT_OCID is not set in .env", file=sys.stderr)
        sys.exit(1)

    response = client.embed_text(
        EmbedTextDetails(
            inputs=texts,
            serving_mode=OnDemandServingMode(model_id=OCI_EMBEDDING_MODEL),
            compartment_id=OCI_COMPARTMENT_OCID,
            input_type="SEARCH_DOCUMENT",
        )
    )
    return response.data.embeddings


def embed_all_chunks(
    client: GenerativeAiInferenceClient, chunks: list[dict]
) -> list[dict]:
    """Add an 'embedding' key to each chunk dict. Processes in batches."""
    texts = [c["chunk_text"] for c in chunks]
    embeddings: list[list[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        print(f"  Embedding chunks {start + 1}–{start + len(batch)} / {len(texts)} ...")
        batch_embeddings = embed_batch(client, batch)
        embeddings.extend(batch_embeddings)

    for chunk, vec in zip(chunks, embeddings):
        chunk["embedding"] = vec

    return chunks


# ── Database insertion ────────────────────────────────────────────────────────

def build_db_connection() -> oracledb.Connection:
    """Open a direct (non-pooled) DB connection for the script."""
    return oracledb.connect(
        user=ADB_USERNAME,
        password=ADB_PASSWORD,
        dsn=ADB_CONNECTION_STRING,
        config_dir=WALLET_DIR,
        wallet_location=WALLET_DIR,
        wallet_password=WALLET_PASSWORD,
    )


def insert_chunks(conn: oracledb.Connection, chunks: list[dict]) -> None:
    """Delete existing rows for each document and insert fresh chunks."""
    doc_names = sorted({c["doc_name"] for c in chunks})

    with conn.cursor() as cur:
        # Clear existing rows for these documents
        for doc_name in doc_names:
            cur.execute(
                "DELETE FROM docs_chunks WHERE doc_name = :dn", dn=doc_name
            )
            print(f"  Cleared existing rows for '{doc_name}'")

        # Insert new chunks using TO_VECTOR() to convert the JSON float array
        insert_sql = (
            "INSERT INTO docs_chunks (doc_name, chunk_text, embedding) "
            "VALUES (:doc_name, :chunk_text, TO_VECTOR(:embedding_json))"
        )

        rows_inserted = 0
        for chunk in chunks:
            embedding_json = json.dumps(chunk["embedding"])
            cur.execute(
                insert_sql,
                doc_name=chunk["doc_name"],
                chunk_text=chunk["chunk_text"],
                embedding_json=embedding_json,
            )
            rows_inserted += 1

        conn.commit()
        print(f"  Committed {rows_inserted} rows to docs_chunks.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== embed_docs.py ===")

    print("\n[1/4] Loading and chunking documents ...")
    chunks = load_chunks()
    print(f"  Total chunks: {len(chunks)}")

    print(f"\n[2/4] Building OCI GenAI client ({OCI_REGION}) ...")
    client = build_genai_client()

    print("\n[3/4] Embedding chunks ...")
    chunks = embed_all_chunks(client, chunks)
    embedding_dim = len(chunks[0]["embedding"]) if chunks else 0
    print(f"  Embedding dimension: {embedding_dim}")

    print("\n[4/4] Inserting into docs_chunks ...")
    conn = build_db_connection()
    try:
        insert_chunks(conn, chunks)
    finally:
        conn.close()

    print("\nDone. Run the verification queries in sql/04_vector_setup.sql to confirm.")


if __name__ == "__main__":
    main()
