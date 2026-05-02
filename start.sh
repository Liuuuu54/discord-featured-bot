#!/bin/bash

# Discord Bot startup script.
# ASCII-only output keeps VPS consoles readable even when UTF-8 is not configured.

set -e

export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

echo "[INFO] Starting Discord Bot..."

if [ -z "$DISCORD_TOKEN" ]; then
    echo "[ERROR] DISCORD_TOKEN is not set"
    exit 1
fi

mkdir -p /app/data/logs

LOG_FILE="/app/data/logs/bot.log"

start_bot() {
    echo "[INFO] Starting bot process..."
    echo "[INFO] Start time: $(date)"
    echo "[INFO] Python version: $(python --version)"
    echo "[INFO] Working directory: $(pwd)"
    echo "[INFO] Data directory: /app/data"
    echo "[INFO] Log file: $LOG_FILE"
    echo "=================================="

    echo "[INFO] Checking Python imports..."
    python -c "import bot; print('[OK] bot.py import succeeded')"
    echo "[INFO] Launching main program..."
    python bot.py
}

cleanup() {
    echo "[INFO] Stop signal received, shutting down bot..."
    exit 0
}

trap cleanup SIGTERM SIGINT

while true; do
    echo "[INFO] Launching bot..."

    if start_bot; then
        echo "[OK] Bot exited normally"
        break
    else
        exit_code=$?
        echo "[ERROR] Bot crashed with exit code: $exit_code"
        echo "[INFO] Restarting in 5 seconds..."
        sleep 5
    fi
done

echo "[INFO] Bot stopped"
