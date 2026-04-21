#!/bin/sh
set -e

# Start ollama serve in background
ollama serve &

# Extract port from OLLAMA_HOST (default 11434)
PORT=$(echo "${OLLAMA_HOST:-0.0.0.0:11434}" | sed 's/.*://')

# Wait for the Ollama API to be ready
until curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/api/tags" | grep -q "200"; do
    echo "Waiting for Ollama API on port ${PORT}..."
    sleep 2
done

echo "Ollama API is ready. Pulling model ${MODEL_NAME}..."
ollama pull "${MODEL_NAME}"

echo "Model ${MODEL_NAME} pulled successfully."

# Keep the container running by waiting on the background process
wait
