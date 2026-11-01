#!/usr/bin/env bash
set -e

echo "========================================================"
echo "       TRUTHMAP AI — Local Development Services"
echo "========================================================"

if [ ! -d "backend" ]; then
    echo "[ERROR] Must run this script from the truthmap-ai root folder."
    exit 1
fi

echo "[1/2] Starting FastAPI Backend on port 8000..."
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

echo "[2/2] Starting Vite Frontend on port 5173..."
cd frontend && npm run dev &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT

echo "Services running. Press Ctrl+C to stop."
wait
