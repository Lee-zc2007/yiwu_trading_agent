#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r backend/requirements.txt
if [[ ! -d frontend/node_modules ]]; then
  npm --prefix frontend install
fi
.venv/bin/python scripts/init_data.py

nohup .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!
(cd frontend && nohup npm run dev > ../frontend.log 2>&1 & echo $! > ../.tradeguard-frontend.pid)
echo "$BACKEND_PID" > .tradeguard-backend.pid

echo "TradeGuard AI 已启动"
echo "前端: http://localhost:3000"
echo "Swagger: http://localhost:8000/docs"
echo "停止服务: ./scripts/stop.sh"
