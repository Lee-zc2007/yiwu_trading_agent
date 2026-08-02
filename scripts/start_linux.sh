#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  python3 -m venv "$PROJECT_ROOT/.venv"
fi

"$PROJECT_ROOT/.venv/bin/python" -m pip install -q -r "$PROJECT_ROOT/backend/requirements.txt"

if [[ ! -d "$PROJECT_ROOT/frontend/node_modules" ]]; then
  (cd "$PROJECT_ROOT/frontend" && npm install)
fi

(cd "$PROJECT_ROOT/backend" && "$PROJECT_ROOT/.venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT INT TERM

echo "Backend: http://localhost:8000 | Swagger: http://localhost:8000/docs"
echo "Frontend: http://localhost:5173 | Press Ctrl+C to stop."
cd "$PROJECT_ROOT/frontend"
npm run dev

