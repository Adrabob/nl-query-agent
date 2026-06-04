#!/usr/bin/env bash
# Launch the FastAPI app. Run from the project root.
# FastAPI also serves the static frontend at / (mounted in backend/main.py),
# so this one process serves both the API and the UI.
set -euo pipefail

uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
