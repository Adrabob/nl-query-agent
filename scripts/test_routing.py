"""Fast classifier-only test: calls router.classify() on labelled questions and
reports route vs expected. Exercises ONLY the intent classifier (no DB, no Select
AI), so it iterates much faster than the full /chat baseline.

Run: uv run python -m scripts.test_routing
"""

from backend.router import classify

# (question, expected_route)
CASES = [
    # --- should be sql (real data the DB has) ---
    ("how many customers do we have?", "sql"),
    ("what is total net revenue by country? top 10", "sql"),
    ("top 10 best-selling products by revenue", "sql"),
    ("which products do customers come back to buy again?", "sql"),
    ("month over month revenue growth by country", "sql"),
    ("top 5 countries by revenue", "sql"),
    ("monthly revenue trend for UK customers in 2011", "sql"),
    ("what is the total value of cancelled orders?", "sql"),
    ("which products have the highest return rate?", "sql"),
    ("who are the top 5 customers by spend?", "sql"),
    # --- should be docs (definitions OR data the dataset lacks) ---
    ("what counts as a return in this dataset?", "docs"),
    ("how is average order value defined?", "docs"),
    ("what currency are the prices in?", "docs"),
    ("what is our gross margin by product?", "docs"),
    ("what was our year over year revenue growth?", "docs"),
    ("what are our current stock levels?", "docs"),
    ("what is the age and gender breakdown of our customers?", "docs"),
    ("which customers are at risk of churning?", "docs"),
    ("what are our average shipping times?", "docs"),
    ("predict next month's revenue", "docs"),
]


def main() -> None:
    passed = 0
    for question, expected in CASES:
        got = classify(question)
        ok = got == expected
        passed += ok
        flag = "PASS" if ok else "FAIL"
        print(f"[{flag}] expected={expected:4} got={got:4}  {question}")
    print(f"\n{passed}/{len(CASES)} passed")


if __name__ == "__main__":
    main()
