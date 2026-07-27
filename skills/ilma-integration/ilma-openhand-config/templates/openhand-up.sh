#!/usr/bin/env bash
# openhand-up — Launch OpenHand (Docker) with backend wrapper-nous + hy3.
# Avoids "stuck at agent settings": persisted settings pre-filled and mounted.
# Use when the local openhands venv is corrupt (version skew) and won't boot.
set -euo pipefail

IMAGE="${OPENHANDS_IMAGE:-docker.openhands.dev/openhands/openhands:1.21.0}"
PERSIST_DIR="/root/.openhands/server"
PORT="${OPENHANDS_PORT:-3000}"

mkdir -p "$PERSIST_DIR"

echo "[openhand-up] Launching $IMAGE"
echo "[openhand-up] Persisted settings: $PERSIST_DIR/settings.json (hy3 @ wrapper-nous:9102)"
echo "[openhand-up] UI: http://localhost:$PORT"

# --network=host so the container can reach wrapper-nous on 127.0.0.1:9102
exec docker run --rm -it --network=host \
  -e "OH_PERSISTENCE_DIR=/persist" \
  -e "LOG_ALL_EVENTS=true" \
  -v "$PERSIST_DIR:/persist" \
  -v "/root/.openhands/skills:/.openhands/skills" \
  "$IMAGE"
