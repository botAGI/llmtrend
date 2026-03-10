#!/usr/bin/env bash
# ============================================================================
# Ollama entrypoint script for the AI Trend Monitor
# ============================================================================
# Starts the Ollama server, waits for it to become ready, then pulls the
# configured model if it is not already available locally.
#
# Environment variables:
#   OLLAMA_MODEL  - Model to pull on startup (default: llama3.1:8b)
# ============================================================================

set -euo pipefail

MODEL="${OLLAMA_MODEL:-llama3.1:8b}"
MAX_RETRIES=30
RETRY_INTERVAL=2

echo "=== Ollama Entrypoint ==="
echo "Model: ${MODEL}"

# ── Start Ollama server in the background ──────────────────────────────────
ollama serve &
SERVER_PID=$!

# ── Wait for server readiness ─────────────────────────────────────────────
echo "Waiting for Ollama server to become ready..."
retries=0
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    retries=$((retries + 1))
    if [ "$retries" -ge "$MAX_RETRIES" ]; then
        echo "ERROR: Ollama server failed to start after ${MAX_RETRIES} attempts."
        exit 1
    fi
    echo "  Attempt ${retries}/${MAX_RETRIES} - server not ready yet..."
    sleep "$RETRY_INTERVAL"
done
echo "Ollama server is ready."

# ── Pull the model if not already present ──────────────────────────────────
if ollama list | grep -q "^${MODEL}"; then
    echo "Model '${MODEL}' is already available."
else
    echo "Pulling model '${MODEL}' (this may take a while on first run)..."
    ollama pull "${MODEL}"
    echo "Model '${MODEL}' pulled successfully."
fi

echo "=== Ollama ready to serve ==="

# ── Keep the server in the foreground ──────────────────────────────────────
wait "$SERVER_PID"
