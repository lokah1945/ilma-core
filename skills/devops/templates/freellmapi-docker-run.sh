#!/usr/bin/env bash
# FreeLLMAPI docker run template — port 3970 (397x-398x range)
# Usage: bash templates/freellmapi-docker-run.sh [port] [container_name]

set -euo pipefail

PORT="${1:-3970}"
NAME="${2:-freellmapi}"
INTERNAL_PORT=3001

# Generate encryption key if not provided
ENCRYPTION_KEY="${ENCRYPTION_KEY:-$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")}"

echo "Starting FreeLLMAPI on 0.0.0.0:${PORT} -> container ${INTERNAL_PORT}"
echo "Container name: ${NAME}"
echo "Encryption key: ${ENCRYPTION_KEY}"

docker run -d \
  --name "${NAME}" \
  --restart unless-stopped \
  -p "0.0.0.0:${PORT}:${INTERNAL_PORT}" \
  -e PORT="${INTERNAL_PORT}" \
  -e NODE_ENV=production \
  -e ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  -e HOST_BIND=0.0.0.0 \
  -v "${NAME}-data:/app/server/data" \
  ghcr.io/tashfeenahmed/freellmapi:latest

echo "Waiting for health check..."
sleep 5
curl -s "http://127.0.0.1:${PORT}/api/ping" | jq .