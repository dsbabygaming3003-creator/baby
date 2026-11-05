#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
RUFF="${RUFF:-$ROOT/.venv/bin/ruff}"
cd "$ROOT"
"$RUFF" check backend/app backend/tests
node --check backend/app/static/app.js
(cd backend && "$PYTHON" -m pytest -q && "$PYTHON" -m alembic upgrade head && "$PYTHON" -m alembic check)
if grep -RIlE '(OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY)[[:space:]]*=[[:space:]]*[A-Za-z0-9_-]{12,}' backend android .env.example; then
  echo 'Potential embedded provider secret found' >&2
  exit 1
fi
echo 'Verification complete: backend, migrations, JavaScript syntax and source secret scan.'
