#!/usr/bin/env bash
# Runs CI's lint and test jobs locally. Keep in step with .github/workflows/ci.yml.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run python release.py check
uv run pytest
