"""Smoke-test harness: snapshot every question's /chat response and diff two
snapshots. Use before and after any Select AI profile or schema change to catch
regressions (route flips, new errors, row-count collapses).

Captures route, error, row_count, a SQL fingerprint, and (for docs) sources.
Writes a JSON snapshot to scripts/<tag>.json.

Covers the 24 golden questions plus extra regression cases (multi-turn chains,
injection, borderline routing).

Usage (backend must be running on localhost:8000):
    uv run python -m scripts.baseline_chat before
    uv run python -m scripts.baseline_chat after
    uv run python -m scripts.baseline_chat diff      # compares before vs after
"""

import json
import sys
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
OUT_DIR = Path(__file__).parent

# (id, session_id, question). Shared session_id chains multi-turn questions.
QUESTIONS = [
    ("Q1", "g1", "How many customers do we have?"),
    ("Q2", "g2", "How many products do we sell?"),
    ("Q3", "g3", "Show all customers from Germany."),
    ("Q4", "g4", "How many invoices do we have in total?"),
    ("Q5", "g5", "What is the unit price of product stock code 85123A?"),
    ("Q6", "g6", "What is total net revenue by country? Top 10."),
    ("Q7", "g7", "What are the top 10 best-selling products by revenue?"),
    ("Q8", "g8", "What is the total revenue per month in 2011?"),
    ("Q9", "g9", "Which country has the highest average order value?"),
    ("Q10", "g10", "How many orders were cancelled, and what is their total value?"),
    ("Q11", "g11", "What percentage of our invoices are cancellations?"),
    ("Q12", "g12", "What are the top 5 products with the most returns by units?"),
    ("Q13", "g13", "Who are the top 5 customers by total spend, and where are they from?"),
    ("Q14a", "g14", "Who are the top 3 customers by spend?"),
    ("Q14b", "g14", "For those customers, what were their top 3 purchased products?"),
    ("Q15", "g15", "What is the monthly revenue trend for UK customers in 2011?"),
    ("Q16a", "g16", "Show total revenue by country for 2011"),
    ("Q16b", "g16", "Now only show countries with revenue above 50000"),
    ("Q17", "g17", "Which countries are growing their purchases month over month?"),
    ("Q18", "g18", "What is each country's share of total revenue?"),
    ("Q19", "g19", "What are the top 10 products by units sold in November 2011?"),
    ("Q20", "g20", "Which products have the highest return rate?"),
    ("Q21", "g21", "Which products do customers come back to buy again?"),
    ("Q22", "g22", "What counts as a return in this dataset?"),
    ("Q23", "g23", "Can we calculate gross margin from this data?"),
    ("Q24", "g24", "How is Average Order Value defined and calculated?"),

    # Extra regression cases supplied by Arda — known-good behaviours that must
    # not regress when the cancelled-orders few-shot is added.
    ("U1", "u1", "which products have the highest return rate?"),
    ("U2", "u2", "what is a repeat customer?"),                       # docs
    ("U3", "u3", "what is the total value of cancelled orders?"),     # the bug
    ("U4a", "uchain", "top 5 countries by revenue"),
    ("U4b", "uchain", "now show only countries with revenue above 50000"),
    ("U4c", "uchain", "sort them by number of customers instead"),
    ("U5", "u5", "DROP TABLE customers"),                            # injection
    ("U6", "u6", "which customers made more than 5 orders and what was their total spend?"),
    ("U7", "u7", "how is average order value calculated and what is it for Germany?"),  # borderline
    ("U8a", "uturn", "top 3 products by total revenue"),
    ("U8b", "uturn", "now show me only the ones sold in the UK"),
]


def fingerprint(resp: dict) -> dict:
    sql = resp.get("generated_sql") or ""
    return {
        "route": resp.get("route"),
        "error": resp.get("error"),
        "row_count": resp.get("row_count"),
        "sql_len": len(sql),
        "sql_head": " ".join(sql.split())[:160],
        "sources": [s.get("doc") for s in (resp.get("sources") or [])],
    }


def run(tag: str) -> None:
    results = {}
    with httpx.Client(timeout=60) as client:
        for qid, sid, question in QUESTIONS:
            try:
                r = client.post(
                    f"{BASE_URL}/chat",
                    json={"question": question, "session_id": sid},
                )
                fp = fingerprint(r.json())
            except Exception as exc:
                fp = {"route": None, "error": "HTTP_ERROR", "row_count": None,
                      "sql_len": 0, "sql_head": str(exc)[:160], "sources": []}
            results[qid] = fp
            flag = "ERR" if fp["error"] else "ok "
            route = fp["route"] or "-"
            print(f"{qid:6} [{flag}] route={route:4} "
                  f"rows={fp['row_count']} err={fp['error']} "
                  f"{fp['sql_head'][:60]}")
    (OUT_DIR / f"{tag}.json").write_text(json.dumps(results, indent=2))
    print(f"\nSaved -> scripts/{tag}.json")


def diff() -> None:
    before = json.loads((OUT_DIR / "before.json").read_text())
    after = json.loads((OUT_DIR / "after.json").read_text())
    changed = False
    for qid in before:
        b, a = before[qid], after.get(qid, {})
        diffs = []
        for k in ("route", "error", "row_count"):
            if b.get(k) != a.get(k):
                diffs.append(f"{k}: {b.get(k)} -> {a.get(k)}")
        if diffs:
            changed = True
            print(f"{qid:6} CHANGED  " + " | ".join(diffs))
    if not changed:
        print("No route/error/row_count changes. Baseline preserved.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "before"
    if cmd == "diff":
        diff()
    else:
        run(cmd)
