#!/usr/bin/env bash
# 启动工作台：只监听本机 127.0.0.1。
cd "$(dirname "$0")/.."
PORT="${STUDIO_PORT:-8000}"

if [ ! -x .venv/bin/python ]; then
  echo "还没安装，先运行 scripts/setup.sh"; exit 1
fi
if [ ! -d frontend/dist ]; then
  (cd frontend && npm run build --silent)
fi

echo "工作台：http://127.0.0.1:${PORT}   （Ctrl+C 退出）"
cd backend
exec ../.venv/bin/python -m uvicorn studio.main:app --host 127.0.0.1 --port "$PORT"
