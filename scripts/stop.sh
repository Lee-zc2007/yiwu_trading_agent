#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
for PID_FILE in .tradeguard-backend.pid .tradeguard-frontend.pid; do
  if [[ -f "$PID_FILE" ]]; then
    PID="$(cat "$PID_FILE")"
    if kill -0 "$PID" 2>/dev/null; then
      kill "$PID"
    fi
    rm -f "$PID_FILE"
  fi
done
echo "TradeGuard AI 服务已停止。"
